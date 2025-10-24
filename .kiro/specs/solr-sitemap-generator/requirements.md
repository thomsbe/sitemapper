# Requirements Document

## Introduction

The Solr Sitemap Generator is a CLI application that extracts document IDs from one or more Solr search cores and generates compressed, split XML sitemaps for search engine crawlers. The application is designed for library catalog systems and other Solr-based applications that need to provide comprehensive sitemaps for millions of documents.

## Glossary

- **Sitemapper**: The CLI application name, invokable via 'uvx sitemapper', built with Python 3.12 and uv
- **Solr Core**: A Solr search index containing documents with unique IDs
- **Document ID**: Unique identifier for a document stored in a Solr core, extracted from configurable ID field
- **ID Field**: Configurable Solr field name containing the document identifiers
- **Date Field**: Configurable Solr field name containing the last modification/indexing date
- **URL Pattern**: Configurable template string for converting document IDs to full URLs
- **Revisit Frequency**: Per-core configurable changefreq value for sitemap entries
- **TOML Configuration**: Configuration file format using .toml extension for specifying cores, fields, and patterns
- **Sitemap XML**: XML file format following the sitemaps.org protocol for search engines
- **Split Sitemap**: Multiple sitemap files when document count exceeds single file limits, processed in parallel
- **Compressed Sitemap**: Gzip-compressed sitemap files to reduce bandwidth
- **Parallel Processing**: Concurrent processing of multiple Solr cores and sitemap generation
- **SystemD Service**: Linux system service for background execution
- **Cron Job**: Scheduled task execution via cron daemon

## Requirements

### Requirement 1

**User Story:** As a library system administrator, I want to generate sitemaps from multiple Solr cores using TOML configuration, so that search engines can discover all catalog entries.

#### Acceptance Criteria

1. THE Sitemapper SHALL read configuration from a TOML file specifying Solr core URLs, ID field names, and URL patterns
2. WHEN the Sitemapper processes each configured Solr core, THE Sitemapper SHALL extract document IDs and last modification dates from the specified fields
3. THE Sitemapper SHALL convert each document ID into a complete URL using the configured URL pattern template
4. THE Sitemapper SHALL include last modification dates and changefreq values in generated sitemap entries
5. THE Sitemapper SHALL generate XML sitemap files conforming to the sitemaps.org protocol with lastmod and changefreq elements
6. WHEN the total number of URLs exceeds 50,000, THE Sitemapper SHALL split the sitemap into multiple files with a sitemap index

### Requirement 2

**User Story:** As a system administrator, I want to run the sitemapper via different execution methods, so that I can integrate it into various deployment scenarios.

#### Acceptance Criteria

1. THE Sitemapper SHALL be installable and executable via 'uvx sitemapper' command
2. THE Sitemapper SHALL support execution as a cron job with appropriate exit codes and logging
3. THE Sitemapper SHALL support execution as a SystemD service with proper service configuration
4. WHEN executed in any mode, THE Sitemapper SHALL provide clear status information and error reporting
5. THE Sitemapper SHALL handle interruption signals gracefully and clean up temporary files

### Requirement 3

**User Story:** As a catalog system operator, I want to process millions of document IDs efficiently with parallel processing, so that sitemap generation completes within reasonable time limits.

#### Acceptance Criteria

1. THE Sitemapper SHALL process document ID extraction from Solr cores in batches to handle large datasets
2. THE Sitemapper SHALL process multiple Solr cores concurrently using parallel processing
3. THE Sitemapper SHALL generate sitemap files in parallel when splitting large datasets
4. THE Sitemapper SHALL provide progress indicators during long-running operations
5. THE Sitemapper SHALL implement memory-efficient processing to handle millions of URLs without excessive RAM usage

### Requirement 4

**User Story:** As a library administrator, I want to configure Solr cores, ID fields, and URL patterns via TOML configuration, so that generated sitemaps match my system's structure and requirements.

#### Acceptance Criteria

1. THE Sitemapper SHALL read TOML configuration files containing Solr core definitions with URL, ID field, date field, URL pattern, and changefreq specifications
2. THE Sitemapper SHALL allow specification of output directory for generated sitemap files in the TOML configuration
3. THE Sitemapper SHALL support configuration file path specification via command-line parameters
4. WHEN no configuration file is specified, THE Sitemapper SHALL look for a default 'sitemapper.toml' file in the current directory
5. THE Sitemapper SHALL validate all TOML configuration parameters before beginning processing

### Requirement 5

**User Story:** As a system operator, I want comprehensive logging and error handling, so that I can monitor sitemap generation and troubleshoot issues effectively.

#### Acceptance Criteria

1. THE Sitemapper SHALL implement structured logging with configurable log levels (DEBUG, INFO, WARNING, ERROR)
2. THE Sitemapper SHALL log all significant operations including core processing start/completion, URL extraction progress, and sitemap generation status
3. WHEN Solr cores are unreachable, THE Sitemapper SHALL log detailed error information and continue with remaining cores
4. THE Sitemapper SHALL provide comprehensive summary statistics including total URLs processed, files generated, processing time, and error counts
5. WHEN run as a service, THE Sitemapper SHALL integrate with system logging facilities and return appropriate exit codes for monitoring systems

### Requirement 6

**User Story:** As a Python developer, I want the application built with modern Python tooling, so that it follows current best practices and is maintainable.

#### Acceptance Criteria

1. THE Sitemapper SHALL be implemented using Python 3.12 as the target runtime version
2. THE Sitemapper SHALL use uv for dependency management and packaging
3. THE Sitemapper SHALL be installable via uvx for easy distribution and execution
4. THE Sitemapper SHALL follow Python packaging standards for CLI applications
5. THE Sitemapper SHALL include proper error handling and type hints throughout the codebase