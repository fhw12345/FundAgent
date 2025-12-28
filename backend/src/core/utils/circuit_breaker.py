"""
Circuit Breaker pattern implementation for tool execution.

Story 1.4: Retry Logic Optimization
- Prevents cascading failures by stopping requests to failing tools
- Three states: CLOSED (normal), OPEN (blocked), HALF_OPEN (testing)
- Tracks failure count and automatically opens circuit on threshold
- Auto-recovery after timeout period

Usage:
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

    try:
        if breaker.can_execute("tool_name"):
            result = await tool_func()
            breaker.record_success("tool_name")
        else:
            raise CircuitBreakerOpenError("tool_name")
    except Exception as e:
        breaker.record_failure("tool_name")
        raise
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for a single circuit breaker."""

    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    last_state_change: float = field(default_factory=time.time)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(self, tool_name: str, time_until_retry: float):
        self.tool_name = tool_name
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit breaker OPEN for '{tool_name}'. Retry in {time_until_retry:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker for tool execution with per-tool tracking.

    Prevents cascading failures by temporarily blocking requests to
    repeatedly failing tools. Uses three-state model:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Tool blocked, requests fail immediately
    - HALF_OPEN: Testing if tool has recovered

    Args:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery (half-open)
        success_threshold: Successes needed in half-open to close circuit
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._circuits: dict[str, CircuitStats] = {}

    def _get_circuit(self, tool_name: str) -> CircuitStats:
        """Get or create circuit stats for a tool."""
        if tool_name not in self._circuits:
            self._circuits[tool_name] = CircuitStats()
        return self._circuits[tool_name]

    def _update_state(self, tool_name: str, circuit: CircuitStats) -> None:
        """Update circuit state based on current conditions."""
        current_time = time.time()

        if circuit.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            time_since_failure = current_time - circuit.last_failure_time
            if time_since_failure >= self.recovery_timeout:
                circuit.state = CircuitState.HALF_OPEN
                circuit.last_state_change = current_time
                circuit.consecutive_failures = 0
                logger.info(
                    "Circuit breaker transitioning to HALF_OPEN",
                    tool_name=tool_name,
                    time_in_open=round(time_since_failure, 1),
                )

    def can_execute(self, tool_name: str) -> bool:
        """
        Check if a tool can be executed.

        Returns True if circuit is CLOSED or HALF_OPEN.
        Returns False if circuit is OPEN.
        """
        circuit = self._get_circuit(tool_name)
        self._update_state(tool_name, circuit)

        if circuit.state == CircuitState.OPEN:
            time_remaining = self.recovery_timeout - (
                time.time() - circuit.last_failure_time
            )
            logger.warning(
                "Circuit breaker blocking execution",
                tool_name=tool_name,
                state=circuit.state.value,
                time_until_retry=round(max(0, time_remaining), 1),
            )
            return False

        return True

    def record_success(self, tool_name: str) -> None:
        """Record a successful execution."""
        circuit = self._get_circuit(tool_name)
        circuit.successes += 1
        circuit.consecutive_failures = 0

        if circuit.state == CircuitState.HALF_OPEN:
            # Check if we've had enough successes to close the circuit
            # In half-open, we count recent successes
            circuit.state = CircuitState.CLOSED
            circuit.last_state_change = time.time()
            logger.info(
                "Circuit breaker CLOSED after successful recovery",
                tool_name=tool_name,
                total_successes=circuit.successes,
            )

        logger.debug(
            "Circuit breaker recorded success",
            tool_name=tool_name,
            state=circuit.state.value,
        )

    def record_failure(self, tool_name: str, error: Exception | None = None) -> None:
        """Record a failed execution."""
        circuit = self._get_circuit(tool_name)
        circuit.failures += 1
        circuit.consecutive_failures += 1
        circuit.last_failure_time = time.time()

        if circuit.state == CircuitState.HALF_OPEN:
            # Failure in half-open immediately reopens circuit
            circuit.state = CircuitState.OPEN
            circuit.last_state_change = time.time()
            logger.warning(
                "Circuit breaker OPENED (failed in half-open)",
                tool_name=tool_name,
                error=str(error) if error else None,
            )
        elif (
            circuit.state == CircuitState.CLOSED
            and circuit.consecutive_failures >= self.failure_threshold
        ):
            # Too many consecutive failures, open the circuit
            circuit.state = CircuitState.OPEN
            circuit.last_state_change = time.time()
            logger.warning(
                "Circuit breaker OPENED (failure threshold reached)",
                tool_name=tool_name,
                consecutive_failures=circuit.consecutive_failures,
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
                error=str(error) if error else None,
            )
        else:
            logger.debug(
                "Circuit breaker recorded failure",
                tool_name=tool_name,
                state=circuit.state.value,
                consecutive_failures=circuit.consecutive_failures,
                error=str(error) if error else None,
            )

    def get_status(self, tool_name: str | None = None) -> dict[str, Any]:
        """
        Get circuit breaker status.

        Args:
            tool_name: Specific tool to get status for, or None for all

        Returns:
            Status dict with state, failures, and timing info
        """
        if tool_name:
            circuit = self._get_circuit(tool_name)
            self._update_state(tool_name, circuit)
            return {
                "tool_name": tool_name,
                "state": circuit.state.value,
                "failures": circuit.failures,
                "successes": circuit.successes,
                "consecutive_failures": circuit.consecutive_failures,
                "last_failure_time": circuit.last_failure_time,
            }

        # Return all circuits
        result = {}
        for name in self._circuits:
            circuit = self._circuits[name]
            self._update_state(name, circuit)
            result[name] = {
                "state": circuit.state.value,
                "failures": circuit.failures,
                "successes": circuit.successes,
                "consecutive_failures": circuit.consecutive_failures,
            }
        return result

    def reset(self, tool_name: str | None = None) -> None:
        """
        Reset circuit breaker state.

        Args:
            tool_name: Specific tool to reset, or None for all
        """
        if tool_name:
            if tool_name in self._circuits:
                del self._circuits[tool_name]
                logger.info("Circuit breaker reset", tool_name=tool_name)
        else:
            self._circuits.clear()
            logger.info("All circuit breakers reset")


# Global circuit breaker instance for tool execution
tool_circuit_breaker = CircuitBreaker(
    failure_threshold=5,  # Open after 5 consecutive failures
    recovery_timeout=60.0,  # Wait 60s before testing recovery
    success_threshold=2,  # Need 2 successes to fully close
)
