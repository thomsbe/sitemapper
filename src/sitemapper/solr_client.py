"""
Solr client for document extraction and core communication.

This module provides async HTTP client functionality for interacting
with Solr search cores.
"""

from typing import List, Optional, Dict, Any
import httpx
import json
from urllib.parse import urljoin
from datetime import datetime

from .types import SolrDocument
from .exceptions import SolrConnectionError
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig


class SolrClient:
    """
    Async HTTP client for Solr core interactions.
    
    Provides methods for health checks, document counting, and batch
    document extraction from Solr cores.
    """
    
    def __init__(self, base_url: str, timeout: int = 30, test_mode: bool = False, circuit_breaker: Optional[CircuitBreaker] = None) -> None:
        """
        Initialize the Solr client.
        
        Args:
            base_url: Base URL of the Solr core
            timeout: Request timeout in seconds
            test_mode: If True, limits document processing to 10 docs per core for testing
            circuit_breaker: Optional circuit breaker for resilient error handling
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.test_mode = test_mode
        self._client: Optional[httpx.AsyncClient] = None
        self.circuit_breaker = circuit_breaker
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client instance."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"Accept": "application/json"}
            )
        return self._client
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an HTTP request to Solr and return parsed JSON response.
        
        Args:
            endpoint: Solr endpoint (e.g., 'select', 'admin/ping')
            params: Query parameters for the request
            
        Returns:
            Parsed JSON response from Solr
            
        Raises:
            SolrConnectionError: If request fails or returns invalid response
        """
        async def _do_request() -> Dict[str, Any]:
            client = await self._get_client()
            url = urljoin(f"{self.base_url}/", endpoint)
            
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    raise SolrConnectionError(f"Invalid JSON response from Solr: {e}")
                    
            except httpx.TimeoutException:
                raise SolrConnectionError(f"Timeout connecting to Solr at {url}")
            except httpx.HTTPStatusError as e:
                raise SolrConnectionError(f"HTTP error {e.response.status_code} from Solr: {e.response.text}")
            except httpx.RequestError as e:
                raise SolrConnectionError(f"Network error connecting to Solr: {e}")
        
        # Use circuit breaker if available
        if self.circuit_breaker:
            return await self.circuit_breaker.call(_do_request)
        else:
            return await _do_request()
    
    async def close(self) -> None:
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    def is_test_mode(self) -> bool:
        """
        Check if the client is running in test mode.
        
        Returns:
            True if test mode is enabled, False otherwise
        """
        return self.test_mode
    
    async def get_total_docs(self, id_field: str) -> int:
        """
        Get the total number of documents in the core.
        
        Args:
            id_field: Name of the ID field to count
            
        Returns:
            Total number of documents (limited to 10 in test mode)
            
        Raises:
            SolrConnectionError: If unable to connect or query Solr
        """
        # In test mode, return maximum of 10 documents
        if self.test_mode:
            params = {
                "q": f"{id_field}:*",  # Query for all documents with the ID field
                "rows": 0,  # Don't return actual documents, just count
                "wt": "json"  # Response format
            }
            
            try:
                response = await self._make_request("select", params)
                actual_count = response["response"]["numFound"]
                return min(actual_count, 10)  # Limit to 10 in test mode
            except KeyError as e:
                raise SolrConnectionError(f"Unexpected response format from Solr: missing {e}")
            except Exception as e:
                raise SolrConnectionError(f"Failed to get document count: {e}")
        
        # Normal mode - return actual count
        params = {
            "q": f"{id_field}:*",  # Query for all documents with the ID field
            "rows": 0,  # Don't return actual documents, just count
            "wt": "json"  # Response format
        }
        
        try:
            response = await self._make_request("select", params)
            return response["response"]["numFound"]
        except KeyError as e:
            raise SolrConnectionError(f"Unexpected response format from Solr: missing {e}")
        except Exception as e:
            raise SolrConnectionError(f"Failed to get document count: {e}")
    
    async def fetch_docs_batch(
        self, 
        id_field: str, 
        date_field: str, 
        start: int, 
        rows: int
    ) -> List[SolrDocument]:
        """
        Fetch a batch of documents from the core.
        
        Args:
            id_field: Name of the field containing document IDs
            date_field: Name of the field containing last modification dates
            start: Starting offset for the batch
            rows: Number of documents to fetch
            
        Returns:
            List of Solr documents (limited in test mode)
            
        Raises:
            SolrConnectionError: If unable to fetch documents
        """
        # In test mode, limit total documents to 10
        if self.test_mode:
            # If start is already >= 10, return empty list
            if start >= 10:
                return []
            # Limit rows to not exceed the 10 document limit
            rows = min(rows, 10 - start)
        
        # Build field list - only request fields we actually need
        # If date_field is empty or None, only request ID field for better performance
        if date_field and date_field.strip():
            field_list = f"{id_field},{date_field}"
        else:
            field_list = id_field
        
        params = {
            "q": f"{id_field}:*",  # Query for all documents with the ID field
            "fl": field_list,  # Only return necessary fields
            "start": start,
            "rows": rows,
            "wt": "json",
            "sort": f"{id_field} asc",  # Consistent ordering for pagination
            "omitHeader": "true"  # Skip response header for smaller payload
        }
        
        try:
            response = await self._make_request("select", params)
            docs = response["response"]["docs"]
            
            solr_documents = []
            for doc in docs:
                # Extract document ID
                doc_id = doc.get(id_field)
                if not doc_id:
                    continue  # Skip documents without ID
                
                # Handle ID field that might be a list (multi-valued field)
                if isinstance(doc_id, list):
                    doc_id = doc_id[0] if doc_id else None
                
                if not doc_id:
                    continue
                
                # Extract and parse date field
                last_modified = None
                date_value = doc.get(date_field)
                if date_value:
                    # Handle date field that might be a list
                    if isinstance(date_value, list):
                        date_value = date_value[0] if date_value else None
                    
                    if date_value:
                        last_modified = self._parse_solr_date(date_value)
                
                solr_documents.append(SolrDocument(
                    id=str(doc_id),
                    last_modified=last_modified
                ))
            
            return solr_documents
            
        except KeyError as e:
            raise SolrConnectionError(f"Unexpected response format from Solr: missing {e}")
        except Exception as e:
            raise SolrConnectionError(f"Failed to fetch document batch: {e}")
    
    def _parse_solr_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse Solr date string to datetime object.
        
        Solr typically returns dates in ISO format like '2023-12-01T10:30:00Z'
        or '2023-12-01T10:30:00.123Z'.
        
        Args:
            date_str: Date string from Solr
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_str:
            return None
            
        try:
            # Handle different Solr date formats
            date_formats = [
                "%Y-%m-%dT%H:%M:%SZ",           # 2023-12-01T10:30:00Z
                "%Y-%m-%dT%H:%M:%S.%fZ",       # 2023-12-01T10:30:00.123Z
                "%Y-%m-%d %H:%M:%S",           # 2023-12-01 10:30:00
                "%Y-%m-%dT%H:%M:%S",           # 2023-12-01T10:30:00
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
                    
            # If none of the standard formats work, try ISO parsing
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
        except (ValueError, TypeError):
            # If all parsing attempts fail, return None
            return None
    
    async def health_check(self) -> bool:
        """
        Check if the Solr core is accessible and healthy.
        
        Returns:
            True if core is accessible, False otherwise
        """
        try:
            # Use Solr's ping endpoint for health check
            response = await self._make_request("admin/ping", {"wt": "json"})
            return response.get("status") == "OK"
        except SolrConnectionError:
            return False
        except Exception:
            return False