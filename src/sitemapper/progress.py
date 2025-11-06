"""
Progress tracking and reporting utilities for long-running operations.

This module provides comprehensive progress tracking, statistics collection,
and reporting functionality for the sitemap generation process.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from threading import Lock

from loguru import logger

from .types import CoreResult, ProcessingResult


@dataclass
class ProgressStats:
    """
    Statistics for tracking processing progress.
    
    Attributes:
        start_time: When processing started
        current_processed: Current number of processed items
        total_items: Total number of items to process
        last_update_time: When progress was last updated
        processing_rate: Items processed per second
        estimated_completion: Estimated completion time
        errors_count: Number of errors encountered
    """
    start_time: float = field(default_factory=time.time)
    current_processed: int = 0
    total_items: int = 0
    last_update_time: float = field(default_factory=time.time)
    processing_rate: float = 0.0
    estimated_completion: Optional[float] = None
    errors_count: int = 0
    
    def update_progress(self, processed: int, total: Optional[int] = None) -> None:
        """
        Update progress statistics.
        
        Args:
            processed: Number of items processed so far
            total: Total number of items (optional, uses existing if not provided)
        """
        current_time = time.time()
        
        self.current_processed = processed
        if total is not None:
            self.total_items = total
        
        # Calculate processing rate
        elapsed_time = current_time - self.start_time
        if elapsed_time > 0:
            self.processing_rate = processed / elapsed_time
        
        # Estimate completion time
        if self.processing_rate > 0 and self.total_items > 0:
            remaining_items = self.total_items - processed
            estimated_seconds = remaining_items / self.processing_rate
            self.estimated_completion = current_time + estimated_seconds
        
        self.last_update_time = current_time
    
    def get_percentage(self) -> float:
        """Get completion percentage."""
        if self.total_items <= 0:
            return 0.0
        return min(100.0, (self.current_processed / self.total_items) * 100)
    
    def get_elapsed_time(self) -> float:
        """Get elapsed processing time in seconds."""
        return time.time() - self.start_time
    
    def get_eta_seconds(self) -> Optional[float]:
        """Get estimated time to completion in seconds."""
        if self.estimated_completion is None:
            return None
        return max(0, self.estimated_completion - time.time())
    
    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta_seconds = self.get_eta_seconds()
        if eta_seconds is None:
            return "Unknown"
        
        if eta_seconds < 60:
            return f"{eta_seconds:.0f}s"
        elif eta_seconds < 3600:
            minutes = eta_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = eta_seconds / 3600
            return f"{hours:.1f}h"
    
    def format_rate(self) -> str:
        """Format processing rate as human-readable string."""
        if self.processing_rate < 1:
            return f"{self.processing_rate:.2f}/s"
        elif self.processing_rate < 1000:
            return f"{self.processing_rate:.1f}/s"
        else:
            return f"{self.processing_rate/1000:.1f}k/s"


@dataclass
class CoreProgress:
    """
    Progress tracking for a single core.
    
    Attributes:
        core_name: Name of the core being processed
        stats: Progress statistics
        phase: Current processing phase
        last_log_time: When progress was last logged
        log_interval: Minimum interval between progress logs (seconds)
    """
    core_name: str
    stats: ProgressStats = field(default_factory=ProgressStats)
    phase: str = "initializing"
    last_log_time: float = 0.0
    log_interval: float = 5.0  # Log progress every 5 seconds minimum
    
    def update(self, processed: int, total: Optional[int] = None, phase: Optional[str] = None) -> None:
        """
        Update core progress.
        
        Args:
            processed: Number of items processed
            total: Total number of items
            phase: Current processing phase
        """
        self.stats.update_progress(processed, total)
        if phase is not None:
            self.phase = phase
        
        # Log progress if enough time has passed
        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval:
            self._log_progress()
            self.last_log_time = current_time
    
    def _log_progress(self) -> None:
        """Log current progress."""
        logger.info(
            "Core processing progress",
            core_name=self.core_name,
            phase=self.phase,
            processed=self.stats.current_processed,
            total=self.stats.total_items,
            percentage=f"{self.stats.get_percentage():.1f}%",
            rate=self.stats.format_rate(),
            eta=self.stats.format_eta(),
            elapsed=f"{self.stats.get_elapsed_time():.1f}s"
        )
    
    def add_error(self) -> None:
        """Record an error."""
        self.stats.errors_count += 1
    
    def complete(self) -> None:
        """Mark processing as complete and log final statistics."""
        self.phase = "completed"
        logger.info(
            "Core processing completed",
            core_name=self.core_name,
            total_processed=self.stats.current_processed,
            total_time=f"{self.stats.get_elapsed_time():.2f}s",
            average_rate=self.stats.format_rate(),
            errors=self.stats.errors_count
        )


class ProgressTracker:
    """
    Centralized progress tracking for all cores and overall processing.
    
    This class manages progress tracking across multiple cores and provides
    aggregated statistics and reporting functionality.
    """
    
    def __init__(self):
        """Initialize the progress tracker."""
        self.core_progress: Dict[str, CoreProgress] = {}
        self.overall_stats = ProgressStats()
        self.lock = Lock()
        self.start_time = time.time()
        
        logger.debug("ProgressTracker initialized")
    
    def register_core(self, core_name: str, total_docs: int) -> Callable[[int, Optional[int], Optional[str]], None]:
        """
        Register a core for progress tracking.
        
        Args:
            core_name: Name of the core
            total_docs: Total number of documents in the core
            
        Returns:
            Progress callback function for the core
        """
        with self.lock:
            self.core_progress[core_name] = CoreProgress(core_name)
            self.core_progress[core_name].stats.total_items = total_docs
            
            # Update overall statistics
            self._update_overall_stats()
        
        logger.debug(
            "Core registered for progress tracking",
            core_name=core_name,
            total_docs=total_docs
        )
        
        def progress_callback(processed: int, total: Optional[int] = None, phase: Optional[str] = None) -> None:
            self.update_core_progress(core_name, processed, total, phase)
        
        return progress_callback
    
    def update_core_progress(
        self, 
        core_name: str, 
        processed: int, 
        total: Optional[int] = None, 
        phase: Optional[str] = None
    ) -> None:
        """
        Update progress for a specific core.
        
        Args:
            core_name: Name of the core
            processed: Number of items processed
            total: Total number of items
            phase: Current processing phase
        """
        with self.lock:
            if core_name in self.core_progress:
                self.core_progress[core_name].update(processed, total, phase)
                self._update_overall_stats()
    
    def add_core_error(self, core_name: str) -> None:
        """
        Record an error for a specific core.
        
        Args:
            core_name: Name of the core where the error occurred
        """
        with self.lock:
            if core_name in self.core_progress:
                self.core_progress[core_name].add_error()
                self._update_overall_stats()
    
    def complete_core(self, core_name: str) -> None:
        """
        Mark a core as completed.
        
        Args:
            core_name: Name of the completed core
        """
        with self.lock:
            if core_name in self.core_progress:
                self.core_progress[core_name].complete()
                self._update_overall_stats()
    
    def _update_overall_stats(self) -> None:
        """Update overall processing statistics."""
        total_processed = sum(cp.stats.current_processed for cp in self.core_progress.values())
        total_items = sum(cp.stats.total_items for cp in self.core_progress.values())
        total_errors = sum(cp.stats.errors_count for cp in self.core_progress.values())
        
        self.overall_stats.update_progress(total_processed, total_items)
        self.overall_stats.errors_count = total_errors
    
    def get_overall_progress(self) -> Dict[str, any]:
        """
        Get overall progress statistics.
        
        Returns:
            Dictionary containing overall progress information
        """
        with self.lock:
            completed_cores = sum(1 for cp in self.core_progress.values() if cp.phase == "completed")
            active_cores = sum(1 for cp in self.core_progress.values() if cp.phase not in ["completed", "initializing"])
            
            return {
                "total_cores": len(self.core_progress),
                "completed_cores": completed_cores,
                "active_cores": active_cores,
                "total_processed": self.overall_stats.current_processed,
                "total_items": self.overall_stats.total_items,
                "percentage": self.overall_stats.get_percentage(),
                "processing_rate": self.overall_stats.processing_rate,
                "elapsed_time": self.overall_stats.get_elapsed_time(),
                "eta": self.overall_stats.format_eta(),
                "errors_count": self.overall_stats.errors_count
            }
    
    def log_overall_progress(self) -> None:
        """Log overall progress across all cores."""
        progress = self.get_overall_progress()
        
        logger.info(
            "Overall processing progress",
            cores_completed=f"{progress['completed_cores']}/{progress['total_cores']}",
            total_processed=progress['total_processed'],
            total_items=progress['total_items'],
            percentage=f"{progress['percentage']:.1f}%",
            rate=self.overall_stats.format_rate(),
            eta=progress['eta'],
            elapsed=f"{progress['elapsed_time']:.1f}s",
            errors=progress['errors_count']
        )
    
    def generate_summary_report(self, processing_result: ProcessingResult) -> Dict[str, any]:
        """
        Generate a comprehensive summary report.
        
        Args:
            processing_result: Final processing result
            
        Returns:
            Dictionary containing detailed summary information
        """
        with self.lock:
            # Core-level statistics
            core_summaries = []
            for result in processing_result.core_results:
                core_progress = self.core_progress.get(result.core_name)
                
                summary = {
                    "core_name": result.core_name,
                    "total_docs": result.total_docs,
                    "processed_docs": result.processed_docs,
                    "success_rate": (result.processed_docs / result.total_docs * 100) if result.total_docs > 0 else 0,
                    "processing_time": result.processing_time,
                    "sitemap_files": len(result.sitemap_files),
                    "errors": len(result.errors),
                    "average_rate": result.processed_docs / result.processing_time if result.processing_time > 0 else 0
                }
                
                if core_progress:
                    summary["errors_during_processing"] = core_progress.stats.errors_count
                
                core_summaries.append(summary)
            
            # Overall statistics
            return {
                "summary": {
                    "total_cores": len(processing_result.core_results),
                    "successful_cores": sum(1 for r in processing_result.core_results if not r.errors),
                    "total_urls": processing_result.total_urls,
                    "total_files": processing_result.total_files,
                    "total_time": processing_result.total_time,
                    "success_rate": processing_result.success_rate,
                    "average_rate": processing_result.total_urls / processing_result.total_time if processing_result.total_time > 0 else 0
                },
                "cores": core_summaries,
                "performance": {
                    "fastest_core": max(core_summaries, key=lambda x: x["average_rate"], default=None),
                    "slowest_core": min(core_summaries, key=lambda x: x["average_rate"], default=None),
                    "most_errors": max(core_summaries, key=lambda x: x["errors"], default=None)
                }
            }


class ReportGenerator:
    """
    Generates formatted reports from processing results and statistics.
    """
    
    @staticmethod
    def format_summary_report(summary: Dict[str, any]) -> str:
        """
        Format a summary report as a human-readable string.
        
        Args:
            summary: Summary data from ProgressTracker.generate_summary_report()
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("SITEMAP GENERATION SUMMARY REPORT")
        lines.append("=" * 60)
        
        # Overall statistics
        overall = summary["summary"]
        lines.append(f"Total Cores Processed: {overall['total_cores']}")
        lines.append(f"Successful Cores: {overall['successful_cores']}")
        lines.append(f"Total URLs Generated: {overall['total_urls']:,}")
        lines.append(f"Total Files Created: {overall['total_files']}")
        lines.append(f"Total Processing Time: {overall['total_time']:.2f}s")
        lines.append(f"Overall Success Rate: {overall['success_rate']:.1f}%")
        lines.append(f"Average Processing Rate: {overall['average_rate']:.1f} URLs/s")
        lines.append("")
        
        # Core details
        lines.append("CORE PROCESSING DETAILS:")
        lines.append("-" * 40)
        
        for core in summary["cores"]:
            lines.append(f"Core: {core['core_name']}")
            lines.append(f"  Documents: {core['processed_docs']:,} / {core['total_docs']:,} ({core['success_rate']:.1f}%)")
            lines.append(f"  Files Generated: {core['sitemap_files']}")
            lines.append(f"  Processing Time: {core['processing_time']:.2f}s")
            lines.append(f"  Rate: {core['average_rate']:.1f} docs/s")
            if core['errors'] > 0:
                lines.append(f"  Errors: {core['errors']}")
            lines.append("")
        
        # Performance highlights
        perf = summary["performance"]
        if perf["fastest_core"]:
            lines.append("PERFORMANCE HIGHLIGHTS:")
            lines.append("-" * 40)
            lines.append(f"Fastest Core: {perf['fastest_core']['core_name']} ({perf['fastest_core']['average_rate']:.1f} docs/s)")
            if perf["slowest_core"] and perf["slowest_core"] != perf["fastest_core"]:
                lines.append(f"Slowest Core: {perf['slowest_core']['core_name']} ({perf['slowest_core']['average_rate']:.1f} docs/s)")
            if perf["most_errors"] and perf["most_errors"]["errors"] > 0:
                lines.append(f"Most Errors: {perf['most_errors']['core_name']} ({perf['most_errors']['errors']} errors)")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)