"""
Configuration management for the Sitemapper application.

This module handles TOML configuration file parsing and validation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .types import AppConfig, SolrCoreConfig, SitemapConfig, ChangeFreq, LogLevel
from .exceptions import ConfigurationError


class ConfigManager:
    """
    Manages application configuration loading and validation.
    
    This class is responsible for parsing TOML configuration files
    and converting them into typed configuration objects.
    """
    
    def __init__(self) -> None:
        """Initialize the configuration manager."""
        pass
    
    def load_config(self, config_path: Path) -> AppConfig:
        """
        Load and validate configuration from a TOML file.
        
        Args:
            config_path: Path to the TOML configuration file
            
        Returns:
            Validated application configuration
            
        Raises:
            ConfigurationError: If configuration is invalid or cannot be loaded
        """
        try:
            if not config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
            
            with open(config_path, "rb") as f:
                config_data = tomllib.load(f)
            
            config = self._parse_config(config_data)
            self.validate_config(config)
            return config
            
        except tomllib.TOMLDecodeError as e:
            raise ConfigurationError(f"Invalid TOML syntax in {config_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from {config_path}: {e}")
    
    def _parse_config(self, config_data: Dict[str, Any]) -> AppConfig:
        """
        Parse raw TOML data into typed configuration objects.
        
        Args:
            config_data: Raw TOML data as dictionary
            
        Returns:
            Parsed application configuration
            
        Raises:
            ConfigurationError: If required sections or fields are missing
        """
        # Parse sitemap configuration
        sitemap_data = config_data.get("sitemap", {})
        sitemap_config = self._parse_sitemap_config(sitemap_data)
        
        # Parse processing configuration
        processing_data = config_data.get("processing", {})
        parallel_workers = processing_data.get("parallel_workers", 4)
        log_level = processing_data.get("log_level", LogLevel.INFO)
        test_mode = processing_data.get("test_mode", False)
        
        # Validate log level
        if log_level not in [level.value for level in LogLevel]:
            raise ConfigurationError(f"Invalid log level: {log_level}")
        
        # Validate test_mode
        if not isinstance(test_mode, bool):
            raise ConfigurationError(f"test_mode must be a boolean, got: {test_mode}")
        
        # Parse cores configuration
        cores_data = config_data.get("cores", [])
        if not cores_data:
            raise ConfigurationError("No cores defined in configuration")
        
        cores = self._parse_cores_config(cores_data)
        
        return AppConfig(
            cores=cores,
            sitemap=sitemap_config,
            parallel_workers=parallel_workers,
            log_level=log_level,
            test_mode=test_mode
        )
    
    def _parse_sitemap_config(self, sitemap_data: Dict[str, Any]) -> SitemapConfig:
        """
        Parse sitemap configuration section.
        
        Args:
            sitemap_data: Sitemap section from TOML
            
        Returns:
            Parsed sitemap configuration
            
        Raises:
            ConfigurationError: If required fields are missing
        """
        output_dir = sitemap_data.get("output_dir")
        if not output_dir:
            raise ConfigurationError("sitemap.output_dir is required")
        
        base_url = sitemap_data.get("base_url")
        if not base_url:
            raise ConfigurationError("sitemap.base_url is required")
        
        return SitemapConfig(
            output_dir=output_dir,
            max_urls_per_file=sitemap_data.get("max_urls_per_file", 50000),
            compress=sitemap_data.get("compress", True),
            base_url=base_url
        )
    
    def _parse_cores_config(self, cores_data: List[Dict[str, Any]]) -> List[SolrCoreConfig]:
        """
        Parse cores configuration section.
        
        Args:
            cores_data: List of core configurations from TOML
            
        Returns:
            List of parsed core configurations
            
        Raises:
            ConfigurationError: If required fields are missing or invalid
        """
        cores = []
        
        for i, core_data in enumerate(cores_data):
            try:
                core = self._parse_single_core_config(core_data)
                cores.append(core)
            except ConfigurationError as e:
                raise ConfigurationError(f"Error in core configuration {i}: {e}")
        
        return cores
    
    def _parse_single_core_config(self, core_data: Dict[str, Any]) -> SolrCoreConfig:
        """
        Parse a single core configuration.
        
        Args:
            core_data: Single core configuration from TOML
            
        Returns:
            Parsed core configuration
            
        Raises:
            ConfigurationError: If required fields are missing or invalid
        """
        # Required fields
        required_fields = ["name", "url", "id_field", "date_field", "url_pattern"]
        for field in required_fields:
            if not core_data.get(field):
                raise ConfigurationError(f"Required field '{field}' is missing")
        
        # Validate changefreq if provided
        changefreq = core_data.get("changefreq", ChangeFreq.WEEKLY)
        if changefreq not in [freq.value for freq in ChangeFreq]:
            raise ConfigurationError(f"Invalid changefreq value: {changefreq}")
        
        # Validate numeric fields
        batch_size = core_data.get("batch_size", 1000)
        timeout = core_data.get("timeout", 30)
        
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ConfigurationError(f"batch_size must be a positive integer, got: {batch_size}")
        
        if not isinstance(timeout, int) or timeout <= 0:
            raise ConfigurationError(f"timeout must be a positive integer, got: {timeout}")
        
        return SolrCoreConfig(
            name=core_data["name"],
            url=core_data["url"],
            id_field=core_data["id_field"],
            date_field=core_data["date_field"],
            url_pattern=core_data["url_pattern"],
            changefreq=changefreq,
            batch_size=batch_size,
            timeout=timeout
        )
    
    def validate_config(self, config: AppConfig) -> None:
        """
        Validate the loaded configuration.
        
        Args:
            config: Application configuration to validate
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        self._validate_sitemap_config(config.sitemap)
        self._validate_processing_config(config)
        self._validate_cores_config(config.cores)
    
    def _validate_sitemap_config(self, sitemap: SitemapConfig) -> None:
        """
        Validate sitemap configuration.
        
        Args:
            sitemap: Sitemap configuration to validate
            
        Raises:
            ConfigurationError: If sitemap configuration is invalid
        """
        # Validate output directory
        if not sitemap.output_dir or not sitemap.output_dir.strip():
            raise ConfigurationError("sitemap.output_dir cannot be empty")
        
        # Validate base URL format
        if not sitemap.base_url or not sitemap.base_url.strip():
            raise ConfigurationError("sitemap.base_url cannot be empty")
        
        if not sitemap.base_url.startswith(('http://', 'https://')):
            raise ConfigurationError("sitemap.base_url must start with http:// or https://")
        
        # Validate max_urls_per_file range
        if sitemap.max_urls_per_file <= 0:
            raise ConfigurationError("sitemap.max_urls_per_file must be greater than 0")
        
        if sitemap.max_urls_per_file > 50000:
            raise ConfigurationError("sitemap.max_urls_per_file cannot exceed 50000 (sitemap protocol limit)")
    
    def _validate_processing_config(self, config: AppConfig) -> None:
        """
        Validate processing configuration.
        
        Args:
            config: Application configuration to validate
            
        Raises:
            ConfigurationError: If processing configuration is invalid
        """
        # Validate parallel workers
        if config.parallel_workers <= 0:
            raise ConfigurationError("parallel_workers must be greater than 0")
        
        if config.parallel_workers > 32:
            raise ConfigurationError("parallel_workers should not exceed 32 for optimal performance")
    
    def _validate_cores_config(self, cores: List[SolrCoreConfig]) -> None:
        """
        Validate cores configuration.
        
        Args:
            cores: List of core configurations to validate
            
        Raises:
            ConfigurationError: If any core configuration is invalid
        """
        if not cores:
            raise ConfigurationError("At least one core must be configured")
        
        core_names = set()
        
        for i, core in enumerate(cores):
            try:
                self._validate_single_core_config(core)
                
                # Check for duplicate core names
                if core.name in core_names:
                    raise ConfigurationError(f"Duplicate core name: {core.name}")
                core_names.add(core.name)
                
            except ConfigurationError as e:
                raise ConfigurationError(f"Error in core configuration {i} ({core.name}): {e}")
    
    def _validate_single_core_config(self, core: SolrCoreConfig) -> None:
        """
        Validate a single core configuration.
        
        Args:
            core: Core configuration to validate
            
        Raises:
            ConfigurationError: If core configuration is invalid
        """
        # Validate core name
        if not core.name or not core.name.strip():
            raise ConfigurationError("Core name cannot be empty")
        
        # Validate Solr URL format
        if not core.url or not core.url.strip():
            raise ConfigurationError("Core URL cannot be empty")
        
        if not core.url.startswith(('http://', 'https://')):
            raise ConfigurationError("Core URL must start with http:// or https://")
        
        # Validate field names
        if not core.id_field or not core.id_field.strip():
            raise ConfigurationError("id_field cannot be empty")
        
        if not core.date_field or not core.date_field.strip():
            raise ConfigurationError("date_field cannot be empty")
        
        # Validate URL pattern
        if not core.url_pattern or not core.url_pattern.strip():
            raise ConfigurationError("url_pattern cannot be empty")
        
        if not core.url_pattern.startswith(('http://', 'https://')):
            raise ConfigurationError("url_pattern must start with http:// or https://")
        
        # Validate URL pattern contains placeholder
        if '{id}' not in core.url_pattern:
            raise ConfigurationError("url_pattern must contain {id} placeholder")
        
        # Validate numeric ranges
        if core.batch_size <= 0:
            raise ConfigurationError("batch_size must be greater than 0")
        
        if core.batch_size > 10000:
            raise ConfigurationError("batch_size should not exceed 10000 for optimal performance")
        
        if core.timeout <= 0:
            raise ConfigurationError("timeout must be greater than 0")
        
        if core.timeout > 300:
            raise ConfigurationError("timeout should not exceed 300 seconds")