"""
Exception classes for the Sitemapper application.

This module defines the base exception hierarchy used throughout the application
for consistent error handling and reporting.
"""

from typing import Optional, Any, Dict


class SitemapperError(Exception):
    """
    Base exception for all sitemapper-related errors.
    
    All custom exceptions in the sitemapper application should inherit from this class
    to provide a consistent error handling interface.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the exception with a message and optional details.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary containing additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Return string representation of the exception."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class ConfigurationError(SitemapperError):
    """
    Exception raised for configuration-related errors.
    
    This includes TOML parsing errors, missing required fields,
    invalid URL patterns, and other configuration validation failures.
    """
    pass


class SolrConnectionError(SitemapperError):
    """
    Exception raised for Solr connectivity issues.
    
    This includes network timeouts, HTTP errors, authentication failures,
    and other issues related to communicating with Solr cores.
    """
    pass


class ProcessingError(SitemapperError):
    """
    Exception raised for data processing errors.
    
    This includes memory issues, file system errors, XML generation failures,
    and other errors that occur during sitemap generation processing.
    """
    pass


class ValidationError(SitemapperError):
    """
    Exception raised for data validation errors.
    
    This includes invalid document IDs, malformed URLs, and other
    data validation failures during processing.
    """
    pass