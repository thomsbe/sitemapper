"""
URL building and validation system for the Sitemapper application.

This module provides functionality to convert document IDs into complete URLs
using configurable URL patterns with placeholder substitution.
"""

import re
from typing import Optional
from urllib.parse import urlparse, quote

from .exceptions import ConfigurationError


class URLBuilder:
    """
    Handles URL pattern template processing and ID-to-URL conversion.
    
    This class provides functionality to:
    - Parse and validate URL patterns with placeholders
    - Convert document IDs to complete URLs using template substitution
    - Validate generated URLs for proper format
    """
    
    def __init__(self, url_pattern: str, base_url: str) -> None:
        """
        Initialize the URL builder with a pattern template.
        
        Args:
            url_pattern: Template string containing {id} placeholder
            base_url: Base URL for the website (used for validation)
            
        Raises:
            ConfigurationError: If the URL pattern is invalid
        """
        self.url_pattern = url_pattern
        self.base_url = base_url
        
        # Pre-compile regex for placeholder detection
        self._placeholder_regex = re.compile(r'\{([^}]+)\}')
        
        # Extract all placeholders from the pattern
        self._placeholders = set(self._placeholder_regex.findall(url_pattern))
        
        # Validate the pattern during initialization
        self.validate_pattern()
    
    def build_url(self, document_id: str) -> str:
        """
        Convert a document ID into a complete URL using the configured pattern.
        
        Args:
            document_id: The document identifier to convert
            
        Returns:
            Complete URL with the document ID substituted
            
        Raises:
            ValueError: If the document ID is empty or invalid
        """
        if not document_id or not document_id.strip():
            raise ValueError("Document ID cannot be empty")
        
        # URL-encode the document ID to handle special characters
        encoded_id = quote(str(document_id), safe='')
        
        # Substitute the {id} placeholder with the encoded document ID
        url = self.url_pattern.replace('{id}', encoded_id)
        
        # Validate the generated URL
        if not self._is_valid_url(url):
            raise ValueError(f"Generated URL is invalid: {url}")
        
        return url
    
    def validate_pattern(self) -> bool:
        """
        Validate the URL pattern for correctness.
        
        Returns:
            True if the pattern is valid
            
        Raises:
            ConfigurationError: If the pattern is invalid
        """
        if not self.url_pattern or not self.url_pattern.strip():
            raise ConfigurationError("URL pattern cannot be empty")
        
        # Check if pattern starts with http:// or https://
        if not self.url_pattern.startswith(('http://', 'https://')):
            raise ConfigurationError("URL pattern must start with http:// or https://")
        
        # Check if pattern contains the required {id} placeholder
        if '{id}' not in self.url_pattern:
            raise ConfigurationError("URL pattern must contain {id} placeholder")
        
        # Check for unsupported placeholders
        supported_placeholders = {'id'}
        unsupported = self._placeholders - supported_placeholders
        if unsupported:
            raise ConfigurationError(
                f"URL pattern contains unsupported placeholders: {', '.join(unsupported)}. "
                f"Only {', '.join(supported_placeholders)} are supported."
            )
        
        # Validate the pattern by testing with a sample ID
        try:
            test_url = self.url_pattern.replace('{id}', 'test-id-123')
            if not self._is_valid_url(test_url):
                raise ConfigurationError(f"URL pattern generates invalid URLs: {test_url}")
        except Exception as e:
            raise ConfigurationError(f"URL pattern validation failed: {e}")
        
        return True
    
    def get_placeholders(self) -> set[str]:
        """
        Get all placeholders found in the URL pattern.
        
        Returns:
            Set of placeholder names (without braces)
        """
        return self._placeholders.copy()
    
    def has_placeholder(self, placeholder: str) -> bool:
        """
        Check if the URL pattern contains a specific placeholder.
        
        Args:
            placeholder: Name of the placeholder to check (without braces)
            
        Returns:
            True if the placeholder exists in the pattern
        """
        return placeholder in self._placeholders
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate if a URL has proper format.
        
        Args:
            url: URL string to validate
            
        Returns:
            True if the URL is valid
        """
        try:
            parsed = urlparse(url)
            
            # Check if scheme and netloc are present
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Check if scheme is http or https
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # Check for basic URL structure
            if not parsed.netloc.strip():
                return False
            
            return True
            
        except Exception:
            return False
    
    def preview_url(self, sample_id: str = "sample-id-123") -> str:
        """
        Generate a preview URL using a sample document ID.
        
        This is useful for configuration validation and testing.
        
        Args:
            sample_id: Sample document ID to use for preview
            
        Returns:
            Preview URL with the sample ID substituted
        """
        return self.build_url(sample_id)
    
    def __str__(self) -> str:
        """String representation of the URL builder."""
        return f"URLBuilder(pattern='{self.url_pattern}')"
    
    def __repr__(self) -> str:
        """Detailed string representation of the URL builder."""
        return f"URLBuilder(url_pattern='{self.url_pattern}', base_url='{self.base_url}')"