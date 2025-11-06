"""
Circuit breaker pattern implementation for resilient Solr connections.

This module provides circuit breaker functionality to handle Solr connection
failures gracefully and prevent cascading failures across multiple cores.
"""

import time
import asyncio
from typing import Optional, Callable, Any, Dict, List
from enum import Enum
from dataclasses import dataclass

from .exceptions import SolrConnectionError
from .logging import get_logger


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: float = 60.0      # Seconds to wait before trying again
    success_threshold: int = 3          # Successes needed to close circuit
    timeout: float = 30.0               # Request timeout in seconds


class CircuitBreaker:
    """
    Circuit breaker implementation for Solr connections.
    
    This class implements the circuit breaker pattern to provide
    resilient error handling for Solr connections, preventing
    cascading failures and allowing graceful degradation.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize the circuit breaker.
        
        Args:
            name: Name of the circuit (for logging)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.logger = get_logger({"component": "circuit_breaker", "circuit_name": name})
        
        self.logger.debug(
            "Circuit breaker initialized",
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
            success_threshold=self.config.success_threshold
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            SolrConnectionError: If circuit is open or function fails
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                self._fail_fast()
        
        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            self._on_success()
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Circuit breaker timeout after {self.config.timeout}s"
            self.logger.warning("Circuit breaker timeout", timeout=self.config.timeout)
            self._on_failure(SolrConnectionError(error_msg))
            raise SolrConnectionError(error_msg)
            
        except Exception as e:
            self.logger.warning("Circuit breaker caught exception", error=str(e))
            self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt reset.
        
        Returns:
            True if circuit should attempt to reset
        """
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit from OPEN to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        
        self.logger.info(
            "Circuit breaker transitioning to HALF_OPEN",
            previous_state="OPEN",
            recovery_timeout=self.config.recovery_timeout
        )
    
    def _fail_fast(self) -> None:
        """Fail fast when circuit is open."""
        time_remaining = self.config.recovery_timeout
        if self.last_failure_time:
            time_remaining = max(0, self.config.recovery_timeout - (time.time() - self.last_failure_time))
        
        error_msg = f"Circuit breaker is OPEN. Retry in {time_remaining:.1f}s"
        self.logger.debug("Circuit breaker failing fast", time_remaining=time_remaining)
        raise SolrConnectionError(error_msg)
    
    def _on_success(self) -> None:
        """Handle successful function execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self, exception: Exception) -> None:
        """
        Handle failed function execution.
        
        Args:
            exception: Exception that caused the failure
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        self.logger.warning(
            "Circuit breaker recorded failure",
            failure_count=self.failure_count,
            exception_type=type(exception).__name__,
            error=str(exception)
        )
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure during half-open immediately opens circuit
            self._transition_to_open()
        
        elif self.state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        previous_state = self.state.value
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        
        self.logger.info(
            "Circuit breaker closed",
            previous_state=previous_state,
            success_threshold=self.config.success_threshold
        )
    
    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        previous_state = self.state.value
        self.state = CircuitState.OPEN
        self.success_count = 0
        
        self.logger.error(
            "Circuit breaker opened",
            previous_state=previous_state,
            failure_count=self.failure_count,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout
        )
    
    def get_state(self) -> CircuitState:
        """
        Get current circuit state.
        
        Returns:
            Current circuit breaker state
        """
        return self.state
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get circuit breaker statistics.
        
        Returns:
            Dictionary containing circuit breaker statistics
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }
    
    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        
        self.logger.info("Circuit breaker manually reset")


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different Solr cores.
    
    This class provides centralized management of circuit breakers
    for multiple Solr cores, allowing for independent failure handling
    per core while maintaining overall system resilience.
    """
    
    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize the circuit breaker manager.
        
        Args:
            default_config: Default configuration for new circuit breakers
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = get_logger({"component": "circuit_breaker_manager"})
    
    def get_circuit_breaker(self, core_name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get or create a circuit breaker for a specific core.
        
        Args:
            core_name: Name of the Solr core
            config: Optional specific configuration for this circuit breaker
            
        Returns:
            Circuit breaker instance for the core
        """
        if core_name not in self.circuit_breakers:
            breaker_config = config or self.default_config
            self.circuit_breakers[core_name] = CircuitBreaker(core_name, breaker_config)
            
            self.logger.debug(
                "Created circuit breaker for core",
                core_name=core_name,
                total_breakers=len(self.circuit_breakers)
            )
        
        return self.circuit_breakers[core_name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all circuit breakers.
        
        Returns:
            Dictionary mapping core names to circuit breaker statistics
        """
        return {
            core_name: breaker.get_stats()
            for core_name, breaker in self.circuit_breakers.items()
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers to initial state."""
        for breaker in self.circuit_breakers.values():
            breaker.reset()
        
        self.logger.info(
            "All circuit breakers reset",
            total_breakers=len(self.circuit_breakers)
        )
    
    def get_healthy_cores(self) -> List[str]:
        """
        Get list of cores with closed circuit breakers.
        
        Returns:
            List of core names with healthy circuit breakers
        """
        return [
            core_name for core_name, breaker in self.circuit_breakers.items()
            if breaker.get_state() == CircuitState.CLOSED
        ]
    
    def get_failed_cores(self) -> List[str]:
        """
        Get list of cores with open circuit breakers.
        
        Returns:
            List of core names with failed circuit breakers
        """
        return [
            core_name for core_name, breaker in self.circuit_breakers.items()
            if breaker.get_state() == CircuitState.OPEN
        ]