# Sitemapper

A CLI application for generating XML sitemaps from Solr search cores.

## Overview

Sitemapper extracts document IDs from one or more Solr cores and generates compressed, split XML sitemaps for search engine crawlers. It's designed for library catalog systems and other Solr-based applications that need to provide comprehensive sitemaps for millions of documents.

## Installation

Install using uvx for easy execution:

```bash
uvx sitemapper --help
```

## Usage

```bash
# Basic usage with default config
sitemapper

# Specify custom configuration file
sitemapper --config /path/to/config.toml

# Override output directory
sitemapper --config config.toml --output /path/to/output

# Dry run to validate configuration
sitemapper --config config.toml --dry-run

# Set log level
sitemapper --log-level DEBUG
```

## Configuration

Create a `sitemapper.toml` configuration file:

```toml
[sitemap]
output_dir = "./sitemaps"
max_urls_per_file = 50000
compress = true
base_url = "https://example.com"

[processing]
parallel_workers = 4
log_level = "INFO"

[[cores]]
name = "main_catalog"
url = "http://solr1:8983/solr/catalog"
id_field = "id"
date_field = "last_indexed"
url_pattern = "https://catalog.example.com/record/{id}"
changefreq = "weekly"
batch_size = 1000
timeout = 30
```

## Features

- **Multi-core Processing**: Process multiple Solr cores in parallel
- **Large Dataset Support**: Memory-efficient batch processing for millions of documents
- **Sitemap Splitting**: Automatic splitting when URL count exceeds limits
- **Compression**: Gzip compression for all generated files
- **Flexible Configuration**: TOML-based configuration with validation
- **Comprehensive Logging**: Structured logging with configurable levels
- **Service Integration**: Support for cron jobs and SystemD services

## Requirements

- Python 3.12+
- Access to Solr cores via HTTP
- Write permissions for output directory

## License

MIT License