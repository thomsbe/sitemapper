"""
Service integration and monitoring for the Sitemapper application.

This module provides service mode functionality, system integration,
comprehensive error reporting, and exit codes for monitoring systems.
"""

import sys
import signal
import os
import time
import atexit
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from enum import IntEnum

from loguru import logger

from .types import ProcessingResult, CoreResult
from .exceptions import SitemapperError, ConfigurationError, ProcessingError
from .logging import get_logger, ContextualLogger


class ExitCode(IntEnum):
    """
    Standard exit codes for the sitemapper application.
    
    These codes follow Unix conventions and provide clear
    status information for monitoring systems.
    """
    SUCCESS = 0                    # All operations completed successfully
    GENERAL_ERROR = 1             # General application error
    CONFIGURATION_ERROR = 2       # Configuration file or validation error
    SOLR_CONNECTION_ERROR = 3     # Solr connectivity issues
    PROCESSING_ERROR = 4          # Data processing or sitemap generation error
    PERMISSION_ERROR = 5          # File system permission issues
    INTERRUPTED = 6               # Process was interrupted (SIGINT/SIGTERM)
    PARTIAL_SUCCESS = 7           # Some cores processed successfully, others failed
    NO_DATA = 8                   # No data to process (empty cores)
    RESOURCE_ERROR = 9            # Insufficient resources (memory, disk space)


class ServiceManager:
    """
    Manages service mode operation and system integration.
    
    This class handles signal management, graceful shutdown,
    resource cleanup, and service-specific logging.
    """
    
    def __init__(self):
        """Initialize the service manager."""
        self.logger = get_logger({"component": "service_manager"})
        self._shutdown_requested = False
        self._cleanup_handlers: List[Callable[[], None]] = []
        self._pid_file: Optional[Path] = None
        self._start_time = time.time()
        self._temp_files: List[Path] = []
        self._resource_monitors: Dict[str, Any] = {}
        
        # Register signal handlers
        self._register_signal_handlers()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)
        
        # Initialize resource monitoring
        self._init_resource_monitoring()
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        def signal_handler(signum: int, frame) -> None:
            signal_name = signal.Signals(signum).name
            self.logger.info(
                "Shutdown signal received",
                signal=signal_name,
                signal_number=signum
            )
            self._shutdown_requested = True
            self._perform_cleanup()
            sys.exit(ExitCode.INTERRUPTED)
        
        # Register handlers for common shutdown signals
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request
        
        # Register SIGHUP handler for log rotation (Unix only)
        if hasattr(signal, 'SIGHUP'):
            def sighup_handler(signum: int, frame) -> None:
                self.logger.info("SIGHUP received, rotating logs")
                # Loguru handles log rotation automatically
                # This is just for logging the event
            
            signal.signal(signal.SIGHUP, sighup_handler)
    
    def create_pid_file(self, pid_file_path: Optional[Path] = None) -> None:
        """
        Create a PID file for service management.
        
        Args:
            pid_file_path: Path to PID file (default: /var/run/sitemapper.pid)
        """
        if pid_file_path is None:
            pid_file_path = Path("/var/run/sitemapper.pid")
        
        try:
            # Ensure directory exists
            pid_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write PID to file
            with open(pid_file_path, 'w') as f:
                f.write(str(os.getpid()))
            
            self._pid_file = pid_file_path
            self.logger.info(
                "PID file created",
                pid_file=str(pid_file_path),
                pid=os.getpid()
            )
            
            # Register cleanup handler
            self.register_cleanup_handler(self._remove_pid_file)
            
        except PermissionError:
            self.logger.warning(
                "Cannot create PID file due to permissions",
                pid_file=str(pid_file_path)
            )
        except Exception as e:
            self.logger.error(
                "Failed to create PID file",
                pid_file=str(pid_file_path),
                error=str(e)
            )
    
    def _remove_pid_file(self) -> None:
        """Remove the PID file if it exists."""
        if self._pid_file and self._pid_file.exists():
            try:
                self._pid_file.unlink()
                self.logger.debug("PID file removed", pid_file=str(self._pid_file))
            except Exception as e:
                self.logger.warning(
                    "Failed to remove PID file",
                    pid_file=str(self._pid_file),
                    error=str(e)
                )
    
    def register_cleanup_handler(self, handler: Callable[[], None]) -> None:
        """
        Register a cleanup handler to be called on shutdown.
        
        Args:
            handler: Function to call during cleanup
        """
        self._cleanup_handlers.append(handler)
    
    def _perform_cleanup(self) -> None:
        """Perform cleanup operations."""
        self.logger.info("Performing cleanup operations")
        
        # Clean up temporary files first
        self._cleanup_temp_files()
        
        # Run registered cleanup handlers
        for handler in self._cleanup_handlers:
            try:
                handler()
            except Exception as e:
                self.logger.error(
                    "Error during cleanup",
                    handler=handler.__name__,
                    error=str(e)
                )
        
        # Log final resource usage
        final_metrics = self.get_resource_usage()
        self.logger.info("Final resource usage", **final_metrics)
    
    def _cleanup_on_exit(self) -> None:
        """Cleanup handler called on normal exit."""
        if not self._shutdown_requested:
            self._perform_cleanup()
    
    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            True if shutdown was requested via signal
        """
        return self._shutdown_requested
    
    def get_uptime(self) -> float:
        """
        Get service uptime in seconds.
        
        Returns:
            Uptime in seconds since service start
        """
        return time.time() - self._start_time
    
    def _init_resource_monitoring(self) -> None:
        """Initialize resource monitoring for service mode."""
        try:
            import psutil
            process = psutil.Process()
            self._resource_monitors = {
                "process": process,
                "initial_memory": process.memory_info().rss,
                "initial_cpu_time": process.cpu_times()
            }
            self.logger.debug("Resource monitoring initialized")
        except ImportError:
            self.logger.debug("psutil not available, resource monitoring disabled")
        except Exception as e:
            self.logger.warning(f"Failed to initialize resource monitoring: {e}")
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage statistics.
        
        Returns:
            Dictionary containing resource usage metrics
        """
        metrics = {
            "uptime_seconds": self.get_uptime(),
            "process_id": os.getpid()
        }
        
        if "process" in self._resource_monitors:
            try:
                process = self._resource_monitors["process"]
                memory_info = process.memory_info()
                cpu_times = process.cpu_times()
                
                metrics.update({
                    "memory_rss_mb": memory_info.rss / 1024 / 1024,
                    "memory_vms_mb": memory_info.vms / 1024 / 1024,
                    "memory_percent": process.memory_percent(),
                    "cpu_percent": process.cpu_percent(),
                    "cpu_user_time": cpu_times.user,
                    "cpu_system_time": cpu_times.system,
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds() if hasattr(process, 'num_fds') else None
                })
                
                # Calculate memory growth
                if "initial_memory" in self._resource_monitors:
                    initial_memory = self._resource_monitors["initial_memory"]
                    memory_growth = (memory_info.rss - initial_memory) / 1024 / 1024
                    metrics["memory_growth_mb"] = memory_growth
                
            except Exception as e:
                self.logger.debug(f"Failed to get resource usage: {e}")
        
        return metrics
    
    def register_temp_file(self, file_path: Path) -> None:
        """
        Register a temporary file for cleanup on shutdown.
        
        Args:
            file_path: Path to temporary file
        """
        self._temp_files.append(file_path)
        self.logger.debug("Temporary file registered", temp_file=str(file_path))
    
    def _cleanup_temp_files(self) -> None:
        """Clean up registered temporary files."""
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    self.logger.debug("Temporary file cleaned up", temp_file=str(temp_file))
            except Exception as e:
                self.logger.warning(
                    "Failed to clean up temporary file",
                    temp_file=str(temp_file),
                    error=str(e)
                )
        
        self._temp_files.clear()
    
    def log_service_start(self, config_file: str, dry_run: bool = False) -> None:
        """
        Log service startup information.
        
        Args:
            config_file: Path to configuration file
            dry_run: Whether running in dry-run mode
        """
        # Get initial resource usage
        initial_metrics = self.get_resource_usage()
        
        # Prepare metrics without conflicting keys
        safe_metrics = {k: v for k, v in initial_metrics.items() 
                       if k not in ['pid', 'process_id', 'config_file', 'dry_run', 'python_version', 'working_directory']}
        
        self.logger.info(
            "Sitemapper service starting",
            config_file=config_file,
            dry_run=dry_run,
            process_id=os.getpid(),
            python_version=sys.version.split()[0],
            working_directory=os.getcwd(),
            **safe_metrics
        )
    
    def log_service_stop(self, exit_code: ExitCode, uptime: Optional[float] = None) -> None:
        """
        Log service shutdown information.
        
        Args:
            exit_code: Exit code for the service
            uptime: Service uptime in seconds
        """
        if uptime is None:
            uptime = self.get_uptime()
        
        # Get final resource metrics
        final_metrics = self.get_resource_usage()
        
        # Prepare metrics without conflicting keys
        safe_metrics = {k: v for k, v in final_metrics.items() 
                       if k not in ['pid', 'process_id', 'exit_code', 'exit_code_name', 'uptime']}
        
        self.logger.info(
            "Sitemapper service stopping",
            exit_code=int(exit_code),
            exit_code_name=exit_code.name,
            uptime=f"{uptime:.2f}s",
            process_id=os.getpid(),
            **safe_metrics
        )
        
        # Log performance summary for monitoring
        if exit_code == ExitCode.SUCCESS:
            self.logger.info(
                "Service completed successfully",
                performance_summary=True,
                **final_metrics
            )
        else:
            self.logger.error(
                "Service completed with errors",
                exit_code=int(exit_code),
                exit_code_name=exit_code.name,
                **final_metrics
            )


class ErrorReporter:
    """
    Provides comprehensive error reporting and analysis.
    
    This class analyzes processing results and provides detailed
    error reports for monitoring and troubleshooting.
    """
    
    def __init__(self):
        """Initialize the error reporter."""
        self.logger = get_logger({"component": "error_reporter"})
    
    def analyze_processing_result(self, result: ProcessingResult) -> Dict[str, Any]:
        """
        Analyze processing result and generate comprehensive error report.
        
        Args:
            result: Processing result to analyze
            
        Returns:
            Dictionary containing error analysis and recommendations
        """
        analysis = {
            "overall_status": self._determine_overall_status(result),
            "success_rate": result.success_rate,
            "total_errors": self._count_total_errors(result),
            "error_categories": self._categorize_errors(result),
            "failed_cores": self._get_failed_cores(result),
            "recommendations": self._generate_recommendations(result),
            "monitoring_metrics": self._generate_monitoring_metrics(result)
        }
        
        return analysis
    
    def _determine_overall_status(self, result: ProcessingResult) -> str:
        """
        Determine overall processing status.
        
        Args:
            result: Processing result
            
        Returns:
            Status string (success, partial_success, failure)
        """
        if result.success_rate == 100.0:
            return "success"
        elif result.success_rate > 0.0:
            return "partial_success"
        else:
            return "failure"
    
    def _count_total_errors(self, result: ProcessingResult) -> int:
        """
        Count total number of errors across all cores.
        
        Args:
            result: Processing result
            
        Returns:
            Total error count
        """
        return sum(len(core.errors) for core in result.core_results)
    
    def _categorize_errors(self, result: ProcessingResult) -> Dict[str, int]:
        """
        Categorize errors by type for analysis.
        
        Args:
            result: Processing result
            
        Returns:
            Dictionary mapping error categories to counts
        """
        categories = {
            "connection_errors": 0,
            "configuration_errors": 0,
            "processing_errors": 0,
            "validation_errors": 0,
            "unknown_errors": 0
        }
        
        for core in result.core_results:
            for error in core.errors:
                error_lower = error.lower()
                
                if any(keyword in error_lower for keyword in 
                       ["connection", "timeout", "network", "unreachable"]):
                    categories["connection_errors"] += 1
                elif any(keyword in error_lower for keyword in 
                         ["configuration", "config", "invalid", "missing"]):
                    categories["configuration_errors"] += 1
                elif any(keyword in error_lower for keyword in 
                         ["processing", "generation", "memory", "disk"]):
                    categories["processing_errors"] += 1
                elif any(keyword in error_lower for keyword in 
                         ["validation", "format", "pattern"]):
                    categories["validation_errors"] += 1
                else:
                    categories["unknown_errors"] += 1
        
        return categories
    
    def _get_failed_cores(self, result: ProcessingResult) -> List[Dict[str, Any]]:
        """
        Get information about failed cores.
        
        Args:
            result: Processing result
            
        Returns:
            List of failed core information
        """
        failed_cores = []
        
        for core in result.core_results:
            if core.errors or core.processed_docs == 0:
                failed_cores.append({
                    "name": core.core_name,
                    "total_docs": core.total_docs,
                    "processed_docs": core.processed_docs,
                    "error_count": len(core.errors),
                    "errors": core.errors,
                    "processing_time": core.processing_time
                })
        
        return failed_cores
    
    def _generate_recommendations(self, result: ProcessingResult) -> List[str]:
        """
        Generate recommendations based on error analysis.
        
        Args:
            result: Processing result
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        error_categories = self._categorize_errors(result)
        
        # Connection error recommendations
        if error_categories["connection_errors"] > 0:
            recommendations.append(
                "Check Solr core connectivity and network configuration. "
                "Verify Solr services are running and accessible."
            )
        
        # Configuration error recommendations
        if error_categories["configuration_errors"] > 0:
            recommendations.append(
                "Review configuration file for invalid settings. "
                "Validate URL patterns, field names, and core configurations."
            )
        
        # Processing error recommendations
        if error_categories["processing_errors"] > 0:
            recommendations.append(
                "Check system resources (memory, disk space). "
                "Consider reducing batch sizes or parallel workers."
            )
        
        # Low success rate recommendations
        if result.success_rate < 50.0:
            recommendations.append(
                "Success rate is critically low. "
                "Review logs for systematic issues and consider running in debug mode."
            )
        elif result.success_rate < 90.0:
            recommendations.append(
                "Success rate is below optimal. "
                "Review failed cores and consider adjusting timeout settings."
            )
        
        # Performance recommendations
        avg_processing_time = (
            sum(core.processing_time for core in result.core_results) / 
            len(result.core_results) if result.core_results else 0
        )
        
        if avg_processing_time > 300:  # 5 minutes
            recommendations.append(
                "Processing time is high. "
                "Consider increasing parallel workers or optimizing Solr queries."
            )
        
        return recommendations
    
    def _generate_monitoring_metrics(self, result: ProcessingResult) -> Dict[str, Any]:
        """
        Generate metrics for monitoring systems.
        
        Args:
            result: Processing result
            
        Returns:
            Dictionary of monitoring metrics
        """
        # Calculate additional performance metrics
        processing_times = [core.processing_time for core in result.core_results]
        urls_per_core = [core.processed_docs for core in result.core_results]
        
        metrics = {
            "cores_total": len(result.core_results),
            "cores_successful": len([c for c in result.core_results if not c.errors]),
            "cores_failed": len([c for c in result.core_results if c.errors]),
            "urls_total": result.total_urls,
            "files_generated": result.total_files,
            "processing_time_total": result.total_time,
            "processing_time_avg": (
                result.total_time / len(result.core_results) 
                if result.core_results else 0
            ),
            "success_rate_pct": result.success_rate,
            "error_rate_pct": 100.0 - result.success_rate
        }
        
        # Add performance statistics
        if processing_times:
            metrics.update({
                "processing_time_min": min(processing_times),
                "processing_time_max": max(processing_times),
                "processing_time_median": sorted(processing_times)[len(processing_times) // 2]
            })
        
        if urls_per_core:
            metrics.update({
                "urls_per_core_avg": sum(urls_per_core) / len(urls_per_core),
                "urls_per_core_min": min(urls_per_core),
                "urls_per_core_max": max(urls_per_core)
            })
        
        # Calculate throughput metrics
        if result.total_time > 0:
            metrics.update({
                "urls_per_second": result.total_urls / result.total_time,
                "cores_per_second": len(result.core_results) / result.total_time
            })
        
        # Add health indicators for monitoring systems
        metrics.update({
            "health_status": self._calculate_health_status(result),
            "alert_level": self._calculate_alert_level(result),
            "performance_grade": self._calculate_performance_grade(result)
        })
        
        return metrics
    
    def _calculate_health_status(self, result: ProcessingResult) -> str:
        """
        Calculate overall health status for monitoring.
        
        Args:
            result: Processing result
            
        Returns:
            Health status string (healthy, degraded, critical)
        """
        if result.success_rate >= 95.0:
            return "healthy"
        elif result.success_rate >= 75.0:
            return "degraded"
        else:
            return "critical"
    
    def _calculate_alert_level(self, result: ProcessingResult) -> str:
        """
        Calculate alert level for monitoring systems.
        
        Args:
            result: Processing result
            
        Returns:
            Alert level (none, warning, critical)
        """
        if result.success_rate >= 90.0:
            return "none"
        elif result.success_rate >= 50.0:
            return "warning"
        else:
            return "critical"
    
    def _calculate_performance_grade(self, result: ProcessingResult) -> str:
        """
        Calculate performance grade based on processing metrics.
        
        Args:
            result: Processing result
            
        Returns:
            Performance grade (A, B, C, D, F)
        """
        # Calculate performance score based on multiple factors
        score = 0
        
        # Success rate (40% of score)
        score += (result.success_rate / 100.0) * 40
        
        # Processing efficiency (30% of score)
        if result.core_results:
            avg_time_per_core = result.total_time / len(result.core_results)
            # Assume good performance is < 60 seconds per core
            efficiency = max(0, min(1, (120 - avg_time_per_core) / 120))
            score += efficiency * 30
        
        # Throughput (20% of score)
        if result.total_time > 0:
            urls_per_second = result.total_urls / result.total_time
            # Assume good throughput is > 100 URLs/second
            throughput_score = min(1, urls_per_second / 100)
            score += throughput_score * 20
        
        # Error rate (10% of score)
        error_count = sum(len(core.errors) for core in result.core_results)
        error_penalty = min(10, error_count)  # Cap penalty at 10 points
        score += max(0, 10 - error_penalty)
        
        # Convert score to grade
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def log_error_report(self, analysis: Dict[str, Any]) -> None:
        """
        Log comprehensive error report.
        
        Args:
            analysis: Error analysis from analyze_processing_result
        """
        self.logger.info(
            "Processing error analysis",
            overall_status=analysis["overall_status"],
            success_rate=f"{analysis['success_rate']:.1f}%",
            total_errors=analysis["total_errors"],
            failed_cores_count=len(analysis["failed_cores"])
        )
        
        # Log error categories
        if analysis["total_errors"] > 0:
            self.logger.warning(
                "Error breakdown by category",
                **analysis["error_categories"]
            )
        
        # Log failed cores
        for failed_core in analysis["failed_cores"]:
            self.logger.error(
                "Core processing failed",
                core_name=failed_core["name"],
                error_count=failed_core["error_count"],
                processed_docs=failed_core["processed_docs"],
                total_docs=failed_core["total_docs"]
            )
            
            # Log individual errors for this core
            for i, error in enumerate(failed_core["errors"]):
                self.logger.error(
                    "Core error detail",
                    core_name=failed_core["name"],
                    error_index=i + 1,
                    error=error
                )
        
        # Log recommendations
        for i, recommendation in enumerate(analysis["recommendations"]):
            self.logger.info(
                "Recommendation",
                recommendation_index=i + 1,
                recommendation=recommendation
            )


def determine_exit_code(result: ProcessingResult, analysis: Dict[str, Any]) -> ExitCode:
    """
    Determine appropriate exit code based on processing result.
    
    Args:
        result: Processing result
        analysis: Error analysis from ErrorReporter
        
    Returns:
        Appropriate exit code for the application
    """
    # Check for complete success
    if result.success_rate == 100.0 and analysis["total_errors"] == 0:
        return ExitCode.SUCCESS
    
    # Check for no data processed
    if result.total_urls == 0:
        # Distinguish between no cores configured vs cores with no data
        if len(result.core_results) == 0:
            return ExitCode.CONFIGURATION_ERROR
        else:
            return ExitCode.NO_DATA
    
    # Check for resource-related issues
    error_categories = analysis["error_categories"]
    
    # Prioritize resource errors as they indicate system issues
    if any("memory" in error.lower() or "disk" in error.lower() 
           for core in result.core_results for error in core.errors):
        return ExitCode.RESOURCE_ERROR
    
    # Check for permission issues
    if any("permission" in error.lower() or "access" in error.lower()
           for core in result.core_results for error in core.errors):
        return ExitCode.PERMISSION_ERROR
    
    # Check for configuration errors (highest priority for failures)
    if error_categories["configuration_errors"] > 0:
        return ExitCode.CONFIGURATION_ERROR
    
    # Check for connection errors
    if error_categories["connection_errors"] > 0:
        # If all cores failed due to connection issues, it's a connection error
        connection_failures = sum(1 for core in result.core_results 
                                if any("connection" in error.lower() or "timeout" in error.lower()
                                      for error in core.errors))
        if connection_failures == len(result.core_results):
            return ExitCode.SOLR_CONNECTION_ERROR
    
    # Check for processing errors
    if error_categories["processing_errors"] > 0:
        return ExitCode.PROCESSING_ERROR
    
    # Check for partial success (some cores succeeded)
    if result.success_rate > 0.0:
        # Use different thresholds for partial success classification
        if result.success_rate >= 50.0:
            return ExitCode.PARTIAL_SUCCESS
        else:
            # Low success rate indicates systematic issues
            if error_categories["connection_errors"] > error_categories["processing_errors"]:
                return ExitCode.SOLR_CONNECTION_ERROR
            else:
                return ExitCode.PROCESSING_ERROR
    
    # Complete failure - determine primary cause
    if error_categories["connection_errors"] > 0:
        return ExitCode.SOLR_CONNECTION_ERROR
    elif error_categories["processing_errors"] > 0:
        return ExitCode.PROCESSING_ERROR
    else:
        return ExitCode.GENERAL_ERROR


def handle_exception_exit_code(exception: Exception) -> ExitCode:
    """
    Determine exit code based on exception type.
    
    Args:
        exception: Exception that caused the application to exit
        
    Returns:
        Appropriate exit code for the exception
    """
    if isinstance(exception, ConfigurationError):
        return ExitCode.CONFIGURATION_ERROR
    elif isinstance(exception, ProcessingError):
        return ExitCode.PROCESSING_ERROR
    elif isinstance(exception, PermissionError):
        return ExitCode.PERMISSION_ERROR
    elif isinstance(exception, MemoryError):
        return ExitCode.RESOURCE_ERROR
    elif isinstance(exception, KeyboardInterrupt):
        return ExitCode.INTERRUPTED
    elif isinstance(exception, SitemapperError):
        return ExitCode.GENERAL_ERROR
    else:
        return ExitCode.GENERAL_ERROR


class MonitoringExporter:
    """
    Exports monitoring metrics in various formats for integration with monitoring systems.
    """
    
    def __init__(self):
        """Initialize the monitoring exporter."""
        self.logger = get_logger({"component": "monitoring_exporter"})
    
    def export_prometheus_metrics(self, metrics: Dict[str, Any], output_file: Optional[Path] = None) -> str:
        """
        Export metrics in Prometheus format.
        
        Args:
            metrics: Monitoring metrics dictionary
            output_file: Optional file to write metrics to
            
        Returns:
            Prometheus-formatted metrics string
        """
        prometheus_lines = []
        
        # Add metadata
        prometheus_lines.append("# HELP sitemapper_processing_info Sitemapper processing information")
        prometheus_lines.append("# TYPE sitemapper_processing_info gauge")
        
        # Convert metrics to Prometheus format
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                metric_name = f"sitemapper_{key}"
                prometheus_lines.append(f"{metric_name} {value}")
        
        # Add labels for categorical metrics
        if "health_status" in metrics:
            health_value = 1 if metrics["health_status"] == "healthy" else 0
            prometheus_lines.append(f'sitemapper_health_status{{status="{metrics["health_status"]}"}} {health_value}')
        
        if "alert_level" in metrics:
            alert_value = {"none": 0, "warning": 1, "critical": 2}.get(metrics["alert_level"], 0)
            prometheus_lines.append(f'sitemapper_alert_level{{level="{metrics["alert_level"]}"}} {alert_value}')
        
        prometheus_output = "\n".join(prometheus_lines) + "\n"
        
        # Write to file if specified
        if output_file:
            try:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    f.write(prometheus_output)
                self.logger.info("Prometheus metrics exported", output_file=str(output_file))
            except Exception as e:
                self.logger.error("Failed to export Prometheus metrics", error=str(e))
        
        return prometheus_output
    
    def export_json_metrics(self, metrics: Dict[str, Any], output_file: Optional[Path] = None) -> str:
        """
        Export metrics in JSON format.
        
        Args:
            metrics: Monitoring metrics dictionary
            output_file: Optional file to write metrics to
            
        Returns:
            JSON-formatted metrics string
        """
        import json
        
        # Add timestamp and metadata
        export_data = {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metrics": metrics,
            "exporter": "sitemapper",
            "version": "1.0.0"
        }
        
        json_output = json.dumps(export_data, indent=2)
        
        # Write to file if specified
        if output_file:
            try:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w') as f:
                    f.write(json_output)
                self.logger.info("JSON metrics exported", output_file=str(output_file))
            except Exception as e:
                self.logger.error("Failed to export JSON metrics", error=str(e))
        
        return json_output
    
    def export_nagios_check(self, result: ProcessingResult, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export metrics in Nagios check format.
        
        Args:
            result: Processing result
            analysis: Error analysis
            
        Returns:
            Dictionary with Nagios check information
        """
        # Determine Nagios status
        success_rate = result.success_rate
        
        if success_rate >= 95.0:
            status = "OK"
            status_code = 0
        elif success_rate >= 75.0:
            status = "WARNING"
            status_code = 1
        else:
            status = "CRITICAL"
            status_code = 2
        
        # Create performance data
        perf_data = [
            f"success_rate={success_rate:.1f}%;75;95;0;100",
            f"total_urls={result.total_urls}",
            f"processing_time={result.total_time:.2f}s",
            f"cores_failed={len(analysis['failed_cores'])}"
        ]
        
        # Create status message
        if status == "OK":
            message = f"Sitemap generation completed successfully - {result.total_urls} URLs processed"
        elif status == "WARNING":
            message = f"Sitemap generation completed with warnings - {success_rate:.1f}% success rate"
        else:
            message = f"Sitemap generation failed - {success_rate:.1f}% success rate, {len(analysis['failed_cores'])} cores failed"
        
        return {
            "status": status,
            "status_code": status_code,
            "message": message,
            "performance_data": "|".join(perf_data),
            "long_output": "\n".join(analysis.get("recommendations", []))
        }


# Global service manager instance
service_manager = ServiceManager()
error_reporter = ErrorReporter()
monitoring_exporter = MonitoringExporter()