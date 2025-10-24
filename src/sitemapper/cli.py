"""
Command-line interface for the Sitemapper application.

This module provides the main CLI entry point using Click for argument parsing
and user interaction.
"""

import click
from typing import Optional


@click.command()
@click.option(
    '--config', '-c', 
    default='sitemapper.toml',
    help='Configuration file path',
    type=click.Path(exists=True, readable=True)
)
@click.option(
    '--output', '-o',
    help='Output directory (overrides config)',
    type=click.Path(file_okay=False, writable=True)
)
@click.option(
    '--log-level',
    default='INFO',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    help='Logging level'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Validate configuration without processing'
)
def main(config: str, output: Optional[str], log_level: str, dry_run: bool) -> None:
    """
    Generate XML sitemaps from Solr search cores.
    
    This tool extracts document IDs from configured Solr cores and generates
    compliant XML sitemap files for search engine crawlers.
    """
    # Implementation will be added in later tasks
    click.echo("Sitemapper CLI - Implementation coming soon!")
    click.echo(f"Config: {config}")
    click.echo(f"Output: {output}")
    click.echo(f"Log Level: {log_level}")
    click.echo(f"Dry Run: {dry_run}")


if __name__ == "__main__":
    main()