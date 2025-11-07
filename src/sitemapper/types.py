"""
Type definitions and data models for the Sitemapper application.

This module contains all the type hints, dataclasses, and type aliases
used throughout the application for better type safety and documentation.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator, Callable
from enum import Enum


class LogLevel(str, Enum):
    """Enumeration of supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ChangeFreq(str, Enum):
    """Enumeration of valid sitemap changefreq values."""
    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NEVER = "never"


@dataclass
class SolrDocument:
    """
    Represents a document extracted from a Solr core.
    
    Attributes:
        id: Unique identifier for the document
        last_modified: Optional last modification timestamp
    """
    id: str
    last_modified: Optional[datetime] = None


@dataclass
class SitemapEntry:
    """
    Represents an entry in a sitemap file.
    
    Attributes:
        url: Complete URL for the sitemap entry
        last_modified: Optional last modification timestamp
        changefreq: How frequently the page is likely to change
    """
    url: str
    last_modified: Optional[datetime] = None
    changefreq: str = ChangeFreq.WEEKLY


@dataclass
class SolrCoreConfig:
    """
    Configuration for a single Solr core.
    
    Attributes:
        name: Human-readable name for the core
        url: Base URL of the Solr core
        id_field: Name of the field containing document IDs
        date_field: Name of the field containing last modification dates
        url_pattern: Template string for converting IDs to URLs
        changefreq: Default changefreq value for sitemap entries
        batch_size: Number of documents to fetch per batch
        timeout: Request timeout in seconds
    """
    name: str
    url: str
    id_field: str
    date_field: str
    url_pattern: str
    changefreq: str = ChangeFreq.WEEKLY
    batch_size: int = 1000
    timeout: int = 30


@dataclass
class SitemapConfig:
    """
    Configuration for sitemap generation.
    
    Attributes:
        output_dir: Directory where sitemap files will be written
        max_urls_per_file: Maximum URLs per sitemap file before splitting
        compress: Whether to gzip compress the generated files
        base_url: Base URL for the website (used for sitemap index)
        output_name: Name for the global sitemap index file (default: sitemap.xml)
    """
    output_dir: str
    max_urls_per_file: int = 50000
    compress: bool = True
    base_url: str = ""
    output_name: str = "sitemap.xml"


@dataclass
class AppConfig:
    """
    Main application configuration.
    
    Attributes:
        cores: List of Solr core configurations
        sitemap: Sitemap generation configuration
        parallel_workers: Number of parallel workers for processing
        log_level: Logging level for the application
        test_mode: If True, limits processing to 10 documents per core for testing
    """
    cores: List[SolrCoreConfig]
    sitemap: SitemapConfig
    parallel_workers: int = 4
    log_level: str = LogLevel.INFO
    test_mode: bool = False


@dataclass
class CoreResult:
    """
    Result of processing a single Solr core.
    
    Attributes:
        core_name: Name of the processed core
        total_docs: Total number of documents in the core
        processed_docs: Number of documents successfully processed
        sitemap_files: List of generated sitemap files
        processing_time: Time taken to process the core in seconds
        errors: List of error messages encountered during processing
    """
    core_name: str
    total_docs: int
    processed_docs: int
    sitemap_files: List[Path]
    processing_time: float
    errors: List[str]


@dataclass
class ProcessingResult:
    """
    Overall result of processing all cores.
    
    Attributes:
        core_results: Results for each processed core
        total_urls: Total number of URLs processed across all cores
        total_files: Total number of sitemap files generated
        total_time: Total processing time in seconds
        success_rate: Percentage of successfully processed documents
    """
    core_results: List[CoreResult]
    total_urls: int
    total_files: int
    total_time: float
    success_rate: float


# Type aliases for better readability
ProgressCallback = Callable[[int, Optional[int], str], None]
DocumentIterator = AsyncIterator[List[SolrDocument]]
SitemapEntryIterator = AsyncIterator[SitemapEntry]
ConfigDict = Dict[str, Any]