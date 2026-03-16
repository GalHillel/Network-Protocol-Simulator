"""
Network Condition Simulator

Provides utilities to inject artificial network impairments such as
packet loss, latency, jitter, bandwidth throttling, and packet reordering.
Used for stress testing and validating protocol reliability mechanisms.
"""

import random
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from .logging_config import setup_logger

logger = setup_logger("core.network_sim")


@dataclass
class NetworkProfile:
    """Configurable network condition profile.

    Attributes:
        loss_rate: Probability of dropping a packet (0.0 – 1.0).
        min_latency_ms: Minimum artificial delay in milliseconds.
        max_latency_ms: Maximum artificial delay in milliseconds.
        bandwidth_kbps: Simulated bandwidth limit in kilobits per second.
                        ``0`` means unlimited.
        reorder_rate: Probability of reordering a packet (0.0 – 1.0).
        duplicate_rate: Probability of duplicating a packet (0.0 – 1.0).
    """

    loss_rate: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    bandwidth_kbps: float = 0.0
    reorder_rate: float = 0.0
    duplicate_rate: float = 0.0

    def __post_init__(self) -> None:
        for attr in ("loss_rate", "reorder_rate", "duplicate_rate"):
            val = getattr(self, attr)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"{attr} must be between 0.0 and 1.0, got {val}")

    @classmethod
    def perfect(cls) -> "NetworkProfile":
        """No network impairments – ideal conditions."""
        return cls()

    @classmethod
    def lossy(cls, loss: float = 0.1) -> "NetworkProfile":
        """Simulate a lossy link (default 10% packet loss)."""
        return cls(loss_rate=loss)

    @classmethod
    def high_latency(cls, latency_ms: float = 200.0) -> "NetworkProfile":
        """Simulate a high-latency link."""
        return cls(min_latency_ms=latency_ms, max_latency_ms=latency_ms * 1.5)

    @classmethod
    def unstable(cls) -> "NetworkProfile":
        """Combination of loss, latency, and reordering."""
        return cls(
            loss_rate=0.15,
            min_latency_ms=50.0,
            max_latency_ms=300.0,
            reorder_rate=0.1,
            duplicate_rate=0.05,
        )


class NetworkConditionSimulator:
    """Applies a :class:`NetworkProfile` to outgoing data.

    Wrap your socket's ``sendto`` calls through :meth:`maybe_send` to
    simulate realistic network conditions.
    """

    def __init__(self, profile: Optional[NetworkProfile] = None) -> None:
        self.profile = profile or NetworkProfile.perfect()
        self._lock = threading.Lock()

    def should_drop(self) -> bool:
        """Return ``True`` if the packet should be dropped."""
        return random.random() < self.profile.loss_rate

    def should_duplicate(self) -> bool:
        """Return ``True`` if the packet should be duplicated."""
        return random.random() < self.profile.duplicate_rate

    def should_reorder(self) -> bool:
        """Return ``True`` if the packet should be delayed for reordering."""
        return random.random() < self.profile.reorder_rate

    def get_latency(self) -> float:
        """Return a random latency (seconds) based on the profile."""
        if self.profile.max_latency_ms <= 0:
            return 0.0
        ms = random.uniform(self.profile.min_latency_ms, self.profile.max_latency_ms)
        return ms / 1000.0

    def apply_bandwidth_delay(self, data_size_bytes: int) -> float:
        """Return additional delay (seconds) based on simulated bandwidth."""
        if self.profile.bandwidth_kbps <= 0:
            return 0.0
        bits = data_size_bytes * 8
        seconds = bits / (self.profile.bandwidth_kbps * 1000)
        return seconds

    def maybe_send(self, send_func, data: bytes, *args, **kwargs) -> bool:
        """Conditionally send data through *send_func* with simulated conditions.

        Args:
            send_func: The actual send/sendto callable.
            data: The data bytes to transmit.
            *args, **kwargs: Forwarded to *send_func*.

        Returns:
            ``True`` if the data was sent (possibly duplicated), ``False``
            if it was dropped.
        """
        if self.should_drop():
            logger.debug("Simulated packet DROP (%d bytes)", len(data))
            return False

        # Latency
        delay = self.get_latency() + self.apply_bandwidth_delay(len(data))
        if delay > 0:
            logger.debug("Simulated delay: %.1f ms", delay * 1000)
            time.sleep(delay)

        send_func(data, *args, **kwargs)

        # Duplicate
        if self.should_duplicate():
            logger.debug("Simulated packet DUPLICATE")
            send_func(data, *args, **kwargs)

        return True
