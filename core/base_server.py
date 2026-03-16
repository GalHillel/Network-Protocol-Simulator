"""
Base Server Abstraction

Provides a common server lifecycle: bind → listen → serve → shutdown.
All protocol servers extend this to ensure consistent graceful shutdown
and signal handling.
"""

import abc
import threading
import logging
from typing import Optional

from core.logging_config import setup_logger


class BaseServer(abc.ABC):
    """Abstract base class for all protocol servers.

    Subclasses must implement :meth:`_serve_forever` which contains the
    main receive/accept loop.  The base class handles lifecycle management
    including graceful shutdown via :meth:`shutdown`.
    """

    def __init__(self, name: str, host: str = "0.0.0.0", port: int = 0) -> None:
        self.name = name
        self.host = host
        self.port = port
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.logger = setup_logger(name)

    @property
    def is_running(self) -> bool:
        """Whether the server is currently accepting requests."""
        return self._running.is_set()

    def start(self, daemon: bool = True) -> None:
        """Start the server in a background thread.

        Args:
            daemon: If ``True``, the server thread will be a daemon thread
                    and will automatically terminate when the main program exits.
        """
        if self.is_running:
            self.logger.warning("%s is already running", self.name)
            return
        self._running.set()
        self._thread = threading.Thread(
            target=self._run_wrapper, name=f"{self.name}-thread", daemon=daemon
        )
        self._thread.start()
        self.logger.info("%s started on %s:%d", self.name, self.host, self.port)

    def _run_wrapper(self) -> None:
        """Wrapper that catches exceptions in the serve loop."""
        try:
            self._serve_forever()
        except Exception:
            self.logger.exception("Unhandled exception in %s", self.name)
        finally:
            self._running.clear()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Signal the server to stop and wait for the thread to finish.

        Args:
            timeout: Maximum seconds to wait for the server thread to exit.
        """
        if not self.is_running:
            return
        self.logger.info("Shutting down %s…", self.name)
        self._running.clear()
        self._cleanup()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self.logger.info("%s stopped.", self.name)

    @abc.abstractmethod
    def _serve_forever(self) -> None:
        """Main server loop.  Must check ``self.is_running`` periodically."""
        ...

    def _cleanup(self) -> None:
        """Hook for subclasses to release resources on shutdown."""
        pass
