"""
Command-line interface for the Sitemapper application.

This module provides the main CLI entry point using Click for argument parsing
and user interaction with comprehensive logging and service integration.
"""

import sys
import os
import click
from pathlib import Path
from typing import Optional

from loguru import logger

from .config import ConfigManager
from .logging import configure_logging, get_logger, LoggingManager
from .service import (
    service_manager, error_reporter, monitoring_exporter, determine_exit_code, 
    handle_exception_exit_code, ExitCode
)
from .types import LogLevel
from .exceptions import SitemapperError, ConfigurationError


@click.command()
@click.option(
    '--config', '-c', 
    default='sitemapper.toml',
    help='Configuration file path',
    type=click.Path(readable=True)
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
    '--log-file',
    help='Path to log file for persistent logging',
    type=click.Path()
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Validate configuration without processing'
)
@click.option(
    '--service-mode',
    is_flag=True,
    help='Run in service/daemon mode with system integration'
)
@click.option(
    '--pid-file',
    help='Path to PID file (service mode only)',
    type=click.Path()
)
@click.option(
    '--no-colors',
    is_flag=True,
    help='Disable colored output'
)
@click.option(
    '--structured-logs',
    is_flag=True,
    default=True,
    help='Use structured logging format (default: enabled)'
)
@click.option(
    '--metrics-output',
    help='Export monitoring metrics to file (JSON format)',
    type=click.Path()
)
@click.option(
    '--prometheus-output',
    help='Export Prometheus metrics to file',
    type=click.Path()
)
@click.option(
    '--nagios-check',
    is_flag=True,
    help='Output Nagios-compatible check results'
)
def main(
    config: str,
    output: Optional[str],
    log_level: str,
    log_file: Optional[str],
    dry_run: bool,
    service_mode: bool,
    pid_file: Optional[str],
    no_colors: bool,
    structured_logs: bool,
    metrics_output: Optional[str],
    prometheus_output: Optional[str],
    nagios_check: bool
) -> None:
    """
    Generate XML sitemaps from Solr search cores.
    
    This tool extracts document IDs from configured Solr cores and generates
    compliant XML sitemap files for search engine crawlers.
    
    Examples:
    
        # Basic usage with default config
        sitemapper
        
        # Specify custom config and output directory
        sitemapper -c /etc/sitemapper/config.toml -o /var/www/sitemaps
        
        # Run in debug mode with file logging
        sitemapper --log-level DEBUG --log-file /var/log/sitemapper.log
        
        # Validate configuration without processing
        sitemapper --dry-run
        
        # Run as service with PID file
        sitemapper --service-mode --pid-file /var/run/sitemapper.pid
    """
    exit_code = ExitCode.SUCCESS
    
    try:
        # Configure logging first
        configure_logging(
            log_level=LogLevel(log_level.upper()),
            log_file=Path(log_file) if log_file else None,
            service_mode=service_mode,
            structured=structured_logs,
            enable_colors=not no_colors
        )
        
        # Get contextual logger for CLI
        cli_logger = get_logger({"component": "cli"})
        
        # Log startup information
        if service_mode:
            service_manager.log_service_start(config, dry_run)
            
            # Create PID file if requested
            if pid_file:
                service_manager.create_pid_file(Path(pid_file))
        
        cli_logger.info(
            "Sitemapper starting",
            config_file=config,
            output_override=output,
            log_level=log_level,
            dry_run=dry_run,
            service_mode=service_mode
        )
        
        # Validate configuration file exists
        config_path = Path(config)
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config}")
        
        # Load and validate configuration
        cli_logger.debug("Loading configuration", config_file=config)
        config_manager = ConfigManager()
        app_config = config_manager.load_config(config_path)
        
        # Override output directory if specified
        if output:
            cli_logger.info("Overriding output directory", output_dir=output)
            app_config.sitemap.output_dir = output
        
        cli_logger.info(
            "Configuration loaded successfully",
            cores_count=len(app_config.cores),
            output_dir=app_config.sitemap.output_dir,
            parallel_workers=app_config.parallel_workers,
            test_mode=app_config.test_mode
        )
        
        # Dry run mode - validate configuration and exit
        if dry_run:
            cli_logger.info("Dry run mode - configuration validation completed")
            click.echo("✓ Configuration validation successful")
            click.echo(f"✓ Found {len(app_config.cores)} configured cores")
            click.echo(f"✓ Output directory: {app_config.sitemap.output_dir}")
            click.echo(f"✓ Parallel workers: {app_config.parallel_workers}")
            
            if app_config.test_mode:
                click.echo("⚠ Test mode enabled - processing limited to 10 documents per core")
            
            # For dry run, create a mock successful result for monitoring tests
            if nagios_check or metrics_output or prometheus_output:
                from .types import ProcessingResult, CoreResult
                
                mock_result = ProcessingResult(
                    core_results=[
                        CoreResult(
                            core_name="dry_run_validation",
                            total_docs=0,
                            processed_docs=0,
                            sitemap_files=[],
                            processing_time=0.1,
                            errors=[]
                        )
                    ],
                    total_urls=0,
                    total_files=0,
                    total_time=0.1,
                    success_rate=100.0
                )
                
                analysis = error_reporter.analyze_processing_result(mock_result)
                monitoring_metrics = analysis["monitoring_metrics"]
                
                if metrics_output:
                    monitoring_exporter.export_json_metrics(
                        monitoring_metrics, 
                        Path(metrics_output)
                    )
                
                if prometheus_output:
                    monitoring_exporter.export_prometheus_metrics(
                        monitoring_metrics,
                        Path(prometheus_output)
                    )
                
                if nagios_check:
                    nagios_result = monitoring_exporter.export_nagios_check(mock_result, analysis)
                    click.echo(f"{nagios_result['status']}: {nagios_result['message']} (dry-run)")
                    if nagios_result['performance_data']:
                        click.echo(f"| {nagios_result['performance_data']}")
            
            return
        
        # Check if shutdown was requested before starting processing
        if service_mode and service_manager.is_shutdown_requested():
            cli_logger.info("Shutdown requested before processing started")
            return
        
        # Import orchestrator here to avoid circular imports
        from .orchestrator import ProcessingOrchestrator
        
        # Initialize and run processing orchestrator
        cli_logger.info("Initializing processing orchestrator")
        orchestrator = ProcessingOrchestrator(app_config)
        
        # Register cleanup for temporary files that might be created during processing
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "sitemapper"
        if temp_dir.exists():
            for temp_file in temp_dir.glob("sitemapper_*"):
                service_manager.register_temp_file(temp_file)
        
        # Run the processing
        cli_logger.info("Starting sitemap generation process")
        
        # Execute the actual processing
        import asyncio
        processing_result = asyncio.run(orchestrator.process_all_cores())
        
        # Analyze results and determine exit code
        analysis = error_reporter.analyze_processing_result(processing_result)
        error_reporter.log_error_report(analysis)
        exit_code = determine_exit_code(processing_result, analysis)
        
        # Export monitoring metrics if requested
        monitoring_metrics = analysis["monitoring_metrics"]
        
        if metrics_output:
            monitoring_exporter.export_json_metrics(
                monitoring_metrics, 
                Path(metrics_output)
            )
        
        if prometheus_output:
            monitoring_exporter.export_prometheus_metrics(
                monitoring_metrics,
                Path(prometheus_output)
            )
        
        if nagios_check:
            nagios_result = monitoring_exporter.export_nagios_check(processing_result, analysis)
            click.echo(f"{nagios_result['status']}: {nagios_result['message']}")
            if nagios_result['performance_data']:
                click.echo(f"| {nagios_result['performance_data']}")
            if nagios_result['long_output']:
                click.echo(nagios_result['long_output'])
        
        cli_logger.info(
            "Sitemap generation completed",
            exit_code=int(exit_code),
            exit_code_name=exit_code.name,
            **monitoring_metrics
        )
        
    except ConfigurationError as e:
        logger.error("Configuration error", error=str(e))
        click.echo(f"Configuration error: {e}", err=True)
        exit_code = ExitCode.CONFIGURATION_ERROR
        
    except SitemapperError as e:
        logger.error("Application error", error=str(e), details=e.details)
        click.echo(f"Application error: {e}", err=True)
        exit_code = handle_exception_exit_code(e)
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        click.echo("\nProcess interrupted by user", err=True)
        exit_code = ExitCode.INTERRUPTED
        
    except Exception as e:
        logger.exception("Unexpected error occurred")
        click.echo(f"Unexpected error: {e}", err=True)
        exit_code = handle_exception_exit_code(e)
        
    finally:
        # Log service stop if in service mode
        if service_mode:
            service_manager.log_service_stop(exit_code)
        
        # Exit with appropriate code
        if exit_code != ExitCode.SUCCESS:
            sys.exit(int(exit_code))


if __name__ == "__main__":
    main()