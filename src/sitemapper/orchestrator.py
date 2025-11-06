"""
Processing orchestrator for coordinating parallel Solr core processing.

This module provides the main coordination logic for processing multiple
Solr cores concurrently and managing the overall sitemap generation workflow.
"""

import asyncio
import time
from typing import List, Dict, Optional, AsyncIterator
from pathlib import Path

from .types import (
    AppConfig, SolrCoreConfig, CoreResult, ProcessingResult, 
    SolrDocument, SitemapEntry, ProgressCallback
)
from .solr_client import SolrClient
from .url_builder import URLBuilder
from .sitemap_generator import SitemapGenerator
from .progress import ProgressTracker, ReportGenerator
from .exceptions import ProcessingError, SolrConnectionError
from .logging import get_logger, ContextualLogger
from .circuit_breaker import CircuitBreakerManager, CircuitBreakerConfig


class ProcessingOrchestrator:
    """
    Coordinates the processing of multiple Solr cores in parallel.
    
    This class manages the overall workflow of extracting documents from
    Solr cores, converting them to sitemap entries, and generating sitemap files.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the processing orchestrator.
        
        Args:
            config: Application configuration containing core and sitemap settings
        """
        self.config = config
        self.sitemap_generator = SitemapGenerator(config.sitemap)
        self.semaphore = asyncio.Semaphore(config.parallel_workers)
        self.progress_tracker = ProgressTracker()
        self.logger = get_logger({"component": "orchestrator"})
        
        # Initialize circuit breaker manager for resilient error handling
        circuit_config = CircuitBreakerConfig(
            failure_threshold=3,      # Open circuit after 3 failures
            recovery_timeout=30.0,    # Wait 30 seconds before retry
            success_threshold=2,      # Need 2 successes to close circuit
            timeout=config.cores[0].timeout if config.cores else 30.0
        )
        self.circuit_breaker_manager = CircuitBreakerManager(circuit_config)
        
        self.logger.info(
            "ProcessingOrchestrator initialized",
            parallel_workers=config.parallel_workers,
            cores_count=len(config.cores),
            test_mode=config.test_mode,
            circuit_breaker_enabled=True
        )
    
    async def process_all_cores(self) -> ProcessingResult:
        """
        Process all configured Solr cores concurrently.
        
        Returns:
            Overall processing result with statistics and core results
            
        Raises:
            ProcessingError: If processing fails for critical reasons
        """
        start_time = time.time()
        
        self.logger.info(
            "Starting parallel processing of all cores",
            cores_count=len(self.config.cores)
        )
        
        # Start periodic overall progress logging
        progress_task = asyncio.create_task(self._log_overall_progress_periodically())
        
        try:
            # Create tasks for processing each core
            tasks = []
            for core_config in self.config.cores:
                task = asyncio.create_task(
                    self._process_core_with_semaphore(core_config)
                )
                tasks.append(task)
            
            # Wait for all cores to complete
            core_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Stop periodic progress logging
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(core_results):
                if isinstance(result, Exception):
                    core_name = self.config.cores[i].name
                    self.logger.error(
                        "Core processing failed with exception",
                        core_name=core_name,
                        error=str(result)
                    )
                    # Create a failed result
                    failed_result = CoreResult(
                        core_name=core_name,
                        total_docs=0,
                        processed_docs=0,
                        sitemap_files=[],
                        processing_time=0.0,
                        errors=[f"Processing failed: {str(result)}"]
                    )
                    processed_results.append(failed_result)
                else:
                    processed_results.append(result)
            
            # Calculate overall statistics
            total_time = time.time() - start_time
            processing_result = self._calculate_overall_result(processed_results, total_time)
            
            # Generate and log comprehensive summary report
            summary_report = self.progress_tracker.generate_summary_report(processing_result)
            formatted_report = ReportGenerator.format_summary_report(summary_report)
            
            self.logger.info(
                "All cores processing completed",
                total_time=f"{total_time:.2f}s",
                total_urls=processing_result.total_urls,
                total_files=processing_result.total_files,
                success_rate=f"{processing_result.success_rate:.1f}%"
            )
            
            # Log the detailed report at INFO level for visibility
            for line in formatted_report.split('\n'):
                if line.strip():
                    self.logger.info(line)
            
            # Log circuit breaker statistics for monitoring
            circuit_stats = self.circuit_breaker_manager.get_all_stats()
            healthy_cores = self.circuit_breaker_manager.get_healthy_cores()
            failed_cores = self.circuit_breaker_manager.get_failed_cores()
            
            self.logger.info(
                "Circuit breaker summary",
                healthy_cores=len(healthy_cores),
                failed_cores=len(failed_cores),
                total_cores=len(circuit_stats)
            )
            
            if failed_cores:
                self.logger.warning(
                    "Some cores failed with circuit breakers open",
                    failed_core_names=failed_cores
                )
            
            return processing_result
            
        except Exception as e:
            # Stop periodic progress logging on error
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
            
            self.logger.error("Critical error during parallel processing", error=str(e))
            raise ProcessingError(f"Failed to process cores: {e}") from e
    
    async def _log_overall_progress_periodically(self) -> None:
        """
        Periodically log overall progress across all cores.
        
        This runs as a background task during processing to provide
        regular updates on the overall progress.
        """
        try:
            while True:
                await asyncio.sleep(30)  # Log overall progress every 30 seconds
                self.progress_tracker.log_overall_progress()
        except asyncio.CancelledError:
            # Task was cancelled, which is expected when processing completes
            pass
    
    async def _process_core_with_semaphore(self, core_config: SolrCoreConfig) -> CoreResult:
        """
        Process a single core with semaphore-based concurrency control.
        
        Args:
            core_config: Configuration for the core to process
            
        Returns:
            Result of processing the core
        """
        async with self.semaphore:
            return await self.process_core(core_config)
    
    async def process_core(self, core_config: SolrCoreConfig) -> CoreResult:
        """
        Process a single Solr core to generate sitemap files.
        
        Args:
            core_config: Configuration for the core to process
            
        Returns:
            Result of processing the core including statistics and generated files
        """
        start_time = time.time()
        errors = []
        
        # Create contextual logger for this core
        core_logger = get_logger({"component": "orchestrator", "core_name": core_config.name})
        
        core_logger.info(
            "Starting core processing",
            core_name=core_config.name,
            core_url=core_config.url
        )
        
        try:
            # Get circuit breaker for this core
            circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(core_config.name)
            
            # Initialize components for this core with circuit breaker
            async with SolrClient(
                core_config.url, 
                core_config.timeout, 
                self.config.test_mode,
                circuit_breaker
            ) as solr_client:
                
                # Health check with retry logic
                health_check_passed = await self._perform_health_check_with_retry(
                    solr_client, core_config, core_logger
                )
                if not health_check_passed:
                    error_msg = f"Core health check failed after retries: {core_config.url}"
                    core_logger.warning("Core health check failed after retries")
                    errors.append(error_msg)
                    # Continue processing anyway - the core might still be functional
                
                # Get total document count
                try:
                    total_docs = await solr_client.get_total_docs(core_config.id_field)
                    core_logger.info(
                        "Core document count retrieved",
                        total_docs=total_docs
                    )
                    
                    # Register core with progress tracker
                    progress_callback = self.progress_tracker.register_core(core_config.name, total_docs)
                    progress_callback(0, total_docs, "document_extraction")
                    
                except SolrConnectionError as e:
                    error_msg = f"Failed to get document count: {e}"
                    core_logger.error(
                        "Failed to get document count",
                        error=str(e),
                        error_type="document_count"
                    )
                    errors.append(error_msg)
                    
                    # Implement graceful degradation - continue with other cores
                    self._handle_core_failure(core_config.name, e, "document_count")
                    
                    return CoreResult(
                        core_name=core_config.name,
                        total_docs=0,
                        processed_docs=0,
                        sitemap_files=[],
                        processing_time=time.time() - start_time,
                        errors=errors
                    )
                
                if total_docs == 0:
                    core_logger.warning("Core has no documents")
                    self.progress_tracker.complete_core(core_config.name)
                    return CoreResult(
                        core_name=core_config.name,
                        total_docs=0,
                        processed_docs=0,
                        sitemap_files=[],
                        processing_time=time.time() - start_time,
                        errors=errors
                    )
                
                # Initialize URL builder
                url_builder = URLBuilder(core_config.url_pattern, self.config.sitemap.base_url)
                
                # Process documents and generate sitemap entries
                sitemap_entries = self._process_documents_to_entries(
                    solr_client, core_config, url_builder, progress_callback
                )
                
                # Update progress to sitemap generation phase
                progress_callback(total_docs, total_docs, "sitemap_generation")
                
                # Generate sitemap files
                sitemap_files = await self.sitemap_generator.generate_sitemaps(
                    sitemap_entries, core_config.name
                )
                
                # Mark core as completed
                self.progress_tracker.complete_core(core_config.name)
                
                processing_time = time.time() - start_time
                
                core_logger.info(
                    "Core processing completed",
                    total_docs=total_docs,
                    sitemap_files_count=len(sitemap_files),
                    processing_time=f"{processing_time:.2f}s",
                    errors_count=len(errors)
                )
                
                return CoreResult(
                    core_name=core_config.name,
                    total_docs=total_docs,
                    processed_docs=total_docs,
                    sitemap_files=sitemap_files,
                    processing_time=processing_time,
                    errors=errors
                )
                
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Core processing failed: {e}"
            core_logger.error(
                "Core processing failed",
                error=str(e),
                error_type="processing"
            )
            errors.append(error_msg)
            
            # Record error in progress tracker
            self.progress_tracker.add_core_error(core_config.name)
            self.progress_tracker.complete_core(core_config.name)
            
            return CoreResult(
                core_name=core_config.name,
                total_docs=0,
                processed_docs=0,
                sitemap_files=[],
                processing_time=processing_time,
                errors=errors
            )
    
    async def _process_documents_to_entries(
        self,
        solr_client: SolrClient,
        core_config: SolrCoreConfig,
        url_builder: URLBuilder,
        progress_callback: ProgressCallback
    ) -> AsyncIterator[SitemapEntry]:
        """
        Process Solr documents and convert them to sitemap entries.
        
        Args:
            solr_client: Solr client for document extraction
            core_config: Core configuration
            url_builder: URL builder for converting IDs to URLs
            progress_callback: Callback for progress reporting
            
        Yields:
            SitemapEntry objects for sitemap generation
        """
        processed_count = 0
        start_offset = 0
        
        while True:
            try:
                # Fetch batch of documents
                documents = await solr_client.fetch_docs_batch(
                    core_config.id_field,
                    core_config.date_field,
                    start_offset,
                    core_config.batch_size
                )
                
                if not documents:
                    # No more documents
                    break
                
                # Convert documents to sitemap entries
                for doc in documents:
                    try:
                        url = url_builder.build_url(doc.id)
                        entry = SitemapEntry(
                            url=url,
                            last_modified=doc.last_modified,
                            changefreq=core_config.changefreq
                        )
                        yield entry
                        processed_count += 1
                        
                    except Exception as e:
                        self.logger.warning(
                            "Failed to process document",
                            core_name=core_config.name,
                            doc_id=doc.id,
                            error=str(e)
                        )
                        # Record error in progress tracker
                        self.progress_tracker.add_core_error(core_config.name)
                        continue
                
                # Update progress
                progress_callback(processed_count, None, "document_extraction")
                
                # Move to next batch
                start_offset += len(documents)
                
                # If we got fewer documents than requested, we're done
                if len(documents) < core_config.batch_size:
                    break
                    
            except SolrConnectionError as e:
                self.logger.error(
                    "Solr connection error during document processing",
                    core_name=core_config.name,
                    offset=start_offset,
                    error=str(e)
                )
                # Record error in progress tracker
                self.progress_tracker.add_core_error(core_config.name)
                
                # Implement retry logic for transient errors
                if "timeout" in str(e).lower() and start_offset < 3 * core_config.batch_size:
                    # For timeout errors in early batches, try smaller batch size
                    reduced_batch_size = max(100, core_config.batch_size // 2)
                    self.logger.info(
                        "Retrying with reduced batch size due to timeout",
                        core_name=core_config.name,
                        original_batch_size=core_config.batch_size,
                        reduced_batch_size=reduced_batch_size
                    )
                    
                    try:
                        # Retry with smaller batch
                        documents = await solr_client.fetch_docs_batch(
                            core_config.id_field,
                            core_config.date_field,
                            start_offset,
                            reduced_batch_size
                        )
                        
                        # Process the smaller batch
                        for doc in documents:
                            try:
                                url = url_builder.build_url(doc.id)
                                entry = SitemapEntry(
                                    url=url,
                                    last_modified=doc.last_modified,
                                    changefreq=core_config.changefreq
                                )
                                yield entry
                                processed_count += 1
                            except Exception as doc_error:
                                self.logger.warning(
                                    "Failed to process document in retry",
                                    core_name=core_config.name,
                                    doc_id=doc.id,
                                    error=str(doc_error)
                                )
                                continue
                        
                        # Update progress and continue
                        progress_callback(processed_count, None, "document_extraction")
                        start_offset += len(documents)
                        continue
                        
                    except Exception as retry_error:
                        self.logger.error(
                            "Retry with reduced batch size also failed",
                            core_name=core_config.name,
                            error=str(retry_error)
                        )
                
                # Skip to next batch if retry failed or not applicable
                start_offset += core_config.batch_size
                continue
                
            except Exception as e:
                self.logger.error(
                    "Unexpected error during document processing",
                    core_name=core_config.name,
                    offset=start_offset,
                    error=str(e)
                )
                # Record error in progress tracker
                self.progress_tracker.add_core_error(core_config.name)
                break
    

    
    async def _perform_health_check_with_retry(
        self,
        solr_client: SolrClient,
        core_config: SolrCoreConfig,
        core_logger: ContextualLogger,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> bool:
        """
        Perform health check with retry logic for transient failures.
        
        Args:
            solr_client: Solr client instance
            core_config: Core configuration
            core_logger: Logger for this core
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if health check passed, False otherwise
        """
        for attempt in range(max_retries + 1):
            try:
                if await solr_client.health_check():
                    if attempt > 0:
                        core_logger.info(
                            "Health check succeeded after retry",
                            attempt=attempt,
                            max_retries=max_retries
                        )
                    return True
                    
            except SolrConnectionError as e:
                if attempt < max_retries:
                    core_logger.warning(
                        "Health check failed, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        error=str(e)
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    core_logger.error(
                        "Health check failed after all retries",
                        max_retries=max_retries,
                        error=str(e)
                    )
            
            except Exception as e:
                core_logger.error(
                    "Unexpected error during health check",
                    attempt=attempt + 1,
                    error=str(e)
                )
                break
        
        return False
    
    def _handle_core_failure(self, core_name: str, error: Exception, phase: str) -> None:
        """
        Handle core failure with graceful degradation.
        
        Args:
            core_name: Name of the failed core
            error: Exception that caused the failure
            phase: Processing phase where failure occurred
        """
        self.logger.warning(
            "Implementing graceful degradation for failed core",
            core_name=core_name,
            phase=phase,
            error_type=type(error).__name__,
            error=str(error)
        )
        
        # Get circuit breaker stats for this core
        circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker(core_name)
        circuit_stats = circuit_breaker.get_stats()
        
        # Log circuit breaker state for monitoring
        self.logger.info(
            "Circuit breaker state for failed core",
            core_name=core_name,
            circuit_state=circuit_stats["state"],
            failure_count=circuit_stats["failure_count"],
            **circuit_stats["config"]
        )
        
        # Record failure in progress tracker
        self.progress_tracker.add_core_error(core_name)
        
        # Check if this is a critical failure pattern
        if isinstance(error, SolrConnectionError):
            if "timeout" in str(error).lower():
                self.logger.warning(
                    "Timeout detected - may indicate network or performance issues",
                    core_name=core_name
                )
            elif "connection" in str(error).lower():
                self.logger.warning(
                    "Connection error detected - core may be down",
                    core_name=core_name
                )
    
    def _calculate_overall_result(
        self, 
        core_results: List[CoreResult], 
        total_time: float
    ) -> ProcessingResult:
        """
        Calculate overall processing statistics from individual core results.
        
        Args:
            core_results: Results from processing individual cores
            total_time: Total processing time in seconds
            
        Returns:
            Overall processing result with aggregated statistics
        """
        total_urls = sum(result.processed_docs for result in core_results)
        total_files = sum(len(result.sitemap_files) for result in core_results)
        total_docs_attempted = sum(result.total_docs for result in core_results)
        
        # Calculate success rate
        if total_docs_attempted > 0:
            success_rate = (total_urls / total_docs_attempted) * 100
        else:
            success_rate = 0.0
        
        return ProcessingResult(
            core_results=core_results,
            total_urls=total_urls,
            total_files=total_files,
            total_time=total_time,
            success_rate=success_rate
        )