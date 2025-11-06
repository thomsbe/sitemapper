"""
Comprehensive logging system for the Sitemapper application.

This module provides structured logging configuration using loguru with
appropriate formatters, levels, and contextual logging for core processing
and error tracking.
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union
from loguru import logger

from .types import LogLevel
from .exceptions import SitemapperError


class LoggingManager:
    """
    Manages application-wide logging configuration and setup.
    
    This class provides centralized logging configuration using loguru
    with structured logging, contextual information, and service integration.
    """
    
    def __init__(self):
        """Initialize the logging manager."""
        self._configured = False
        self._log_file_path: Optional[Path] = None
        self._service_mode = False
    
    def configure_logging(
        self,
        log_level: Union[str, LogLevel] = LogLevel.INFO,
        log_file: Optional[Union[str, Path]] = None,
        service_mode: bool = False,
        structured: bool = True,
        enable_colors: Optional[bool] = None
    ) -> None:
        """
        Configure loguru-based structured logging for the application.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            log_file: Optional path to log file for persistent logging
            service_mode: If True, configure for service/daemon mode
            structured: If True, use structured JSON-like logging format
            enable_colors: If True, enable colored output (auto-detected if None)
        """
        if self._configured:
            logger.warning("Logging already configured, reconfiguring...")
            self.reset_logging()
        
        # Convert log level to string if needed
        if isinstance(log_level, LogLevel):
            log_level = log_level.value
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if log_level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {log_level}. Must be one of {valid_levels}")
        
        log_level = log_level.upper()
        self._service_mode = service_mode
        
        # Auto-detect color support if not specified
        if enable_colors is None:
            enable_colors = self._should_enable_colors(service_mode)
        
        # Remove default logger
        logger.remove()
        
        # Configure console logging
        self._configure_console_logging(log_level, structured, enable_colors, service_mode)
        
        # Configure file logging if requested
        if log_file:
            self._configure_file_logging(log_file, log_level, structured)
        
        # Configure service logging if in service mode
        if service_mode:
            self._configure_service_logging(log_level)
        
        self._configured = True
        
        # Log initial configuration message
        logger.info(
            "Logging system configured",
            log_level=log_level,
            service_mode=service_mode,
            structured=structured,
            colors_enabled=enable_colors,
            log_file=str(log_file) if log_file else None
        )
    
    def _should_enable_colors(self, service_mode: bool) -> bool:
        """
        Determine if colors should be enabled based on environment.
        
        Args:
            service_mode: If True, running in service mode
            
        Returns:
            True if colors should be enabled
        """
        # Disable colors in service mode
        if service_mode:
            return False
        
        # Check if stdout is a TTY
        if not sys.stdout.isatty():
            return False
        
        # Check environment variables
        if os.getenv("NO_COLOR"):
            return False
        
        if os.getenv("FORCE_COLOR"):
            return True
        
        # Check TERM environment variable
        term = os.getenv("TERM", "")
        if "color" in term.lower() or term in ["xterm", "xterm-256color", "screen"]:
            return True
        
        return False
    
    def _configure_console_logging(
        self,
        log_level: str,
        structured: bool,
        enable_colors: bool,
        service_mode: bool
    ) -> None:
        """
        Configure console logging output.
        
        Args:
            log_level: Logging level
            structured: If True, use structured format
            enable_colors: If True, enable colored output
            service_mode: If True, running in service mode
        """
        if structured:
            # Structured format with contextual information
            if enable_colors:
                format_string = (
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                )
            else:
                format_string = (
                    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                )
            
            # Add extra fields if present
            if enable_colors:
                format_string += " | <blue>{extra}</blue>"
            else:
                format_string += " | {extra}"
        else:
            # Simple format for service mode or when structured logging is disabled
            if enable_colors:
                format_string = (
                    "<green>{time:HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<level>{message}</level>"
                )
            else:
                format_string = "{time:HH:mm:ss} | {level: <8} | {message}"
        
        # Configure console handler
        logger.add(
            sys.stderr if service_mode else sys.stdout,
            format=format_string,
            level=log_level,
            colorize=enable_colors,
            backtrace=log_level == "DEBUG",
            diagnose=log_level == "DEBUG",
            enqueue=True,  # Thread-safe logging
            catch=True     # Catch exceptions in logging
        )
    
    def _configure_file_logging(
        self,
        log_file: Union[str, Path],
        log_level: str,
        structured: bool
    ) -> None:
        """
        Configure file-based logging.
        
        Args:
            log_file: Path to log file
            log_level: Logging level
            structured: If True, use structured format
        """
        log_path = Path(log_file)
        self._log_file_path = log_path
        
        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Structured format for file logging (always without colors)
        if structured:
            format_string = (
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message} | {extra}"
            )
        else:
            format_string = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
        
        # Configure file handler with rotation
        logger.add(
            str(log_path),
            format=format_string,
            level=log_level,
            rotation="10 MB",      # Rotate when file reaches 10MB
            retention="7 days",    # Keep logs for 7 days
            compression="gz",      # Compress rotated logs
            backtrace=True,        # Include backtrace in file logs
            diagnose=True,         # Include variable values in file logs
            enqueue=True,          # Thread-safe logging
            catch=True             # Catch exceptions in logging
        )
    
    def _configure_service_logging(self, log_level: str) -> None:
        """
        Configure system logging integration for service mode.
        
        Args:
            log_level: Logging level
        """
        try:
            # Try to configure syslog handler for Unix systems
            import syslog
            
            # Map loguru levels to syslog priorities
            level_mapping = {
                "DEBUG": syslog.LOG_DEBUG,
                "INFO": syslog.LOG_INFO,
                "WARNING": syslog.LOG_WARNING,
                "ERROR": syslog.LOG_ERR
            }
            
            # Open syslog connection with proper identification
            syslog.openlog("sitemapper", syslog.LOG_PID | syslog.LOG_CONS, syslog.LOG_DAEMON)
            
            # Create custom syslog handler with enhanced formatting
            def syslog_handler(record):
                """Custom handler for syslog integration with structured data."""
                try:
                    # Simple approach - just get the message and level
                    if hasattr(record, 'levelname'):
                        level = record.levelname
                        message = record.getMessage()
                    else:
                        level_obj = record.get("level", "INFO")
                        level = level_obj.name if hasattr(level_obj, 'name') else str(level_obj)
                        message = record.get("message", "")
                    
                    priority = level_mapping.get(level, syslog.LOG_INFO)
                    syslog.syslog(priority, f"sitemapper: {message}")
                except Exception:
                    # Fallback - just log a simple message
                    syslog.syslog(syslog.LOG_INFO, "sitemapper: log message error")
            
            # Add syslog handler
            logger.add(
                syslog_handler,
                level=log_level,
                format="{message}",  # Syslog adds its own timestamp
                catch=True,
                filter=lambda record: record["level"].name in level_mapping
            )
            
            # Log successful syslog configuration
            logger.info("System logging integration configured", facility="daemon")
            
        except ImportError:
            # Syslog not available (e.g., on Windows)
            logger.warning("Syslog not available, skipping system logging integration")
        except Exception as e:
            logger.warning(f"Failed to configure syslog: {e}")
    
    def reset_logging(self) -> None:
        """Reset logging configuration by removing all handlers."""
        logger.remove()
        self._configured = False
        self._log_file_path = None
        self._service_mode = False
    
    def add_context(self, **kwargs) -> None:
        """
        Add contextual information to all subsequent log messages.
        
        Args:
            **kwargs: Key-value pairs to add as context
        """
        logger.configure(extra=kwargs)
    
    def get_log_file_path(self) -> Optional[Path]:
        """
        Get the path to the current log file.
        
        Returns:
            Path to log file if file logging is configured, None otherwise
        """
        return self._log_file_path
    
    def is_service_mode(self) -> bool:
        """
        Check if logging is configured for service mode.
        
        Returns:
            True if in service mode
        """
        return self._service_mode


class ContextualLogger:
    """
    Provides contextual logging with automatic context management.
    
    This class wraps loguru logger to provide automatic context
    management for core processing and error tracking.
    """
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """
        Initialize contextual logger.
        
        Args:
            context: Optional initial context to add to all log messages
        """
        self.context = context or {}
        self._logger = logger.bind(**self.context)
    
    def bind(self, **kwargs) -> 'ContextualLogger':
        """
        Create a new contextual logger with additional context.
        
        Args:
            **kwargs: Additional context to bind
            
        Returns:
            New contextual logger with combined context
        """
        new_context = {**self.context, **kwargs}
        return ContextualLogger(new_context)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with context."""
        self._logger.bind(**kwargs).debug(message)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with context."""
        self._logger.bind(**kwargs).info(message)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with context."""
        self._logger.bind(**kwargs).warning(message)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with context."""
        self._logger.bind(**kwargs).error(message)
    
    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback and context."""
        self._logger.bind(**kwargs).exception(message)
    
    def log_core_start(self, core_name: str, core_url: str, total_docs: int) -> None:
        """
        Log the start of core processing with standardized context.
        
        Args:
            core_name: Name of the core being processed
            core_url: URL of the Solr core
            total_docs: Total number of documents in the core
        """
        self.info(
            "Core processing started",
            core_name=core_name,
            core_url=core_url,
            total_docs=total_docs,
            phase="start"
        )
    
    def log_core_progress(
        self,
        core_name: str,
        processed: int,
        total: int,
        phase: str = "processing"
    ) -> None:
        """
        Log core processing progress with standardized context.
        
        Args:
            core_name: Name of the core being processed
            processed: Number of documents processed
            total: Total number of documents
            phase: Current processing phase
        """
        progress_pct = (processed / total * 100) if total > 0 else 0
        
        self.debug(
            "Core processing progress",
            core_name=core_name,
            processed=processed,
            total=total,
            progress_pct=f"{progress_pct:.1f}%",
            phase=phase
        )
    
    def log_core_completion(
        self,
        core_name: str,
        processed_docs: int,
        files_generated: int,
        processing_time: float,
        errors: int = 0
    ) -> None:
        """
        Log core processing completion with standardized context.
        
        Args:
            core_name: Name of the core that was processed
            processed_docs: Number of documents successfully processed
            files_generated: Number of sitemap files generated
            processing_time: Time taken to process the core
            errors: Number of errors encountered
        """
        self.info(
            "Core processing completed",
            core_name=core_name,
            processed_docs=processed_docs,
            files_generated=files_generated,
            processing_time=f"{processing_time:.2f}s",
            errors=errors,
            phase="complete"
        )
    
    def log_core_error(
        self,
        core_name: str,
        error: Union[str, Exception],
        phase: str = "processing"
    ) -> None:
        """
        Log core processing error with standardized context.
        
        Args:
            core_name: Name of the core where error occurred
            error: Error message or exception
            phase: Processing phase where error occurred
        """
        error_msg = str(error)
        if isinstance(error, SitemapperError):
            # Include additional details for custom exceptions
            extra_context = {"error_details": error.details} if error.details else {}
        else:
            extra_context = {}
        
        self.error(
            "Core processing error",
            core_name=core_name,
            error=error_msg,
            phase=phase,
            **extra_context
        )


# Global logging manager instance
logging_manager = LoggingManager()

# Convenience function for getting contextual logger
def get_logger(context: Optional[Dict[str, Any]] = None) -> ContextualLogger:
    """
    Get a contextual logger instance.
    
    Args:
        context: Optional context to bind to the logger
        
    Returns:
        Contextual logger instance
    """
    return ContextualLogger(context)


# Convenience functions for common logging operations
def configure_logging(
    log_level: Union[str, LogLevel] = LogLevel.INFO,
    log_file: Optional[Union[str, Path]] = None,
    service_mode: bool = False,
    structured: bool = True,
    enable_colors: Optional[bool] = None
) -> None:
    """
    Configure application logging.
    
    This is a convenience function that delegates to the global logging manager.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file for persistent logging
        service_mode: If True, configure for service/daemon mode
        structured: If True, use structured JSON-like logging format
        enable_colors: If True, enable colored output (auto-detected if None)
    """
    logging_manager.configure_logging(
        log_level=log_level,
        log_file=log_file,
        service_mode=service_mode,
        structured=structured,
        enable_colors=enable_colors
    )


def reset_logging() -> None:
    """Reset logging configuration."""
    logging_manager.reset_logging()


def add_logging_context(**kwargs) -> None:
    """
    Add contextual information to all subsequent log messages.
    
    Args:
        **kwargs: Key-value pairs to add as context
    """
    logging_manager.add_context(**kwargs)