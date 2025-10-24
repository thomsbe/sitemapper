# Implementation Plan

- [x] 1. Set up project structure and core interfaces
  - Create Python package structure with src/sitemapper layout
  - Set up pyproject.toml with uv configuration and dependencies (click, loguru, httpx, tomli, lxml)
  - Define base exception classes and type hints
  - _Requirements: 6.2, 6.4, 6.5_

- [x] 2. Implement configuration management system
  - [x] 2.1 Create TOML configuration parser and data models
    - Implement SolrCoreConfig with id_field, date_field, and changefreq support
    - Add SitemapConfig and AppConfig dataclasses with TOML parsing
    - _Requirements: 1.1, 4.1, 4.4_
  
  - [x] 2.2 Add configuration validation logic
    - Validate required fields, URL formats, and numeric ranges
    - Implement URL pattern validation with placeholder checking
    - _Requirements: 4.5, 1.1_

- [x] 3. Build Solr client with connection management
  - [x] 3.1 Implement async Solr HTTP client
    - Create SolrClient class with httpx for async requests
    - Add methods for health checks and document counting
    - _Requirements: 3.1, 5.3_
  
  - [x] 3.2 Add batch document extraction functionality
    - Implement paginated document fetching for ID and date fields with configurable batch sizes
    - Add SolrDocument dataclass for ID and last_modified data
    - Add error handling for network timeouts and HTTP errors
    - _Requirements: 1.2, 3.1, 3.5_

- [ ] 4. Create URL building and validation system
  - [ ] 4.1 Implement URL pattern template engine
    - Create URLBuilder class for ID-to-URL conversion
    - Support placeholder substitution in URL patterns
    - _Requirements: 1.3, 4.1_
  
  - [ ]* 4.2 Add URL validation and testing utilities
    - Validate generated URLs for proper format
    - Create test utilities for URL pattern verification
    - _Requirements: 1.3_

- [ ] 5. Develop sitemap generation engine
  - [ ] 5.1 Implement XML sitemap creation with metadata
    - Create SitemapGenerator class with lxml for XML generation
    - Generate compliant sitemap.xml files with lastmod and changefreq elements
    - Add SitemapEntry dataclass for URL, last_modified, and changefreq data
    - _Requirements: 1.4, 1.5, 1.6_
  
  - [ ] 5.2 Add sitemap splitting and compression
    - Implement file splitting when URL count exceeds 50,000
    - Add gzip compression for all generated files
    - Create sitemap index files for split sitemaps
    - _Requirements: 1.5, 3.3_

- [ ] 6. Build parallel processing orchestrator
  - [ ] 6.1 Create processing coordination system
    - Implement ProcessingOrchestrator for managing multiple cores
    - Add async coordination for concurrent core processing
    - _Requirements: 3.2, 3.3_
  
  - [ ] 6.2 Add progress tracking and reporting
    - Implement progress indicators for long-running operations
    - Create result aggregation and statistics collection
    - _Requirements: 3.4, 5.4_

- [ ] 7. Implement comprehensive logging system
  - [ ] 7.1 Set up loguru-based structured logging
    - Configure loguru with appropriate formatters and levels
    - Add contextual logging for core processing and error tracking
    - _Requirements: 5.1, 5.2_
  
  - [ ] 7.2 Add service integration and monitoring
    - Implement system logging integration for service mode
    - Add comprehensive error reporting and exit codes
    - _Requirements: 5.5, 2.4_

- [ ] 8. Create CLI interface with click
  - [ ] 8.1 Implement main CLI command structure
    - Create click-based command interface with options for config, output, log-level
    - Add dry-run mode for configuration validation
    - _Requirements: 2.1, 4.3_
  
  - [ ] 8.2 Add signal handling and cleanup
    - Implement graceful shutdown on SIGINT/SIGTERM
    - Add temporary file cleanup on interruption
    - _Requirements: 2.5_

- [ ] 9. Integrate all components and add error handling
  - [ ] 9.1 Wire together all processing components
    - Connect CLI → Config → Orchestrator → Solr Client → Sitemap Generator
    - Implement end-to-end processing flow from document extraction to sitemap generation with metadata
    - Add proper error propagation and data transformation between components
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  
  - [ ] 9.2 Add resilient error handling patterns
    - Implement circuit breaker for Solr connections
    - Add graceful degradation when cores are unreachable
    - _Requirements: 5.3, 3.5_

- [ ]* 10. Create comprehensive test suite
  - [ ]* 10.1 Write unit tests for core functionality
    - Test configuration parsing, URL building, and sitemap generation
    - Mock Solr responses for client testing
    - _Requirements: 6.5_
  
  - [ ]* 10.2 Add integration and performance tests
    - Test end-to-end processing with mock Solr instances
    - Add performance benchmarks for large dataset processing
    - _Requirements: 3.4, 3.5_

- [ ] 11. Finalize packaging and deployment configuration
  - [ ] 11.1 Complete pyproject.toml and package metadata
    - Finalize entry points, dependencies, and package configuration
    - Ensure uvx compatibility and proper CLI registration
    - _Requirements: 6.2, 6.3, 2.1_
  
  - [ ] 11.2 Create service configuration templates
    - Add SystemD service file template
    - Create example cron configuration
    - _Requirements: 2.2, 2.3_