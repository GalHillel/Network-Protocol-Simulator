"""
Socket Lifecycle Manager

Provides a context-managed socket wrapper that guarantees proper cleanup,
configurable timeouts, and structured logging of socket events.
"""

import socket as _socket
import logging
from typing import Optional, Tuple

from core.logging_config import setup_logger

logger = setup_logger("core.socket")


class ManagedSocket:
    """Context-managed socket wrapper with automatic cleanup.

    Ensures sockets are properly closed even on exceptions, and provides
    convenience methods for common networking patterns.

    Example::

        with ManagedSocket(_socket.AF_INET, _socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", 5353))
            data, addr = sock.recvfrom(512)
    """

    def __init__(
        self,
        family: int = _socket.AF_INET,
        sock_type: int = _socket.SOCK_STREAM,
        timeout: Optional[float] = None,
        reuse_addr: bool = True,
    ) -> None:
        self._socket = _socket.socket(family, sock_type)
        if reuse_addr:
            self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        if timeout is not None:
            self._socket.settimeout(timeout)
        self._closed = False

    @property
    def raw_socket(self) -> _socket.socket:
        """Return the underlying raw socket."""
        return self._socket

    def bind(self, address: Tuple[str, int]) -> None:
        """Bind socket to *address*."""
        self._socket.bind(address)
        logger.debug("Bound to %s:%d", *address)

    def listen(self, backlog: int = 5) -> None:
        """Start listening for connections."""
        self._socket.listen(backlog)

    def accept(self) -> Tuple[_socket.socket, Tuple[str, int]]:
        """Accept an incoming connection."""
        return self._socket.accept()

    def connect(self, address: Tuple[str, int]) -> None:
        """Connect to a remote address."""
        self._socket.connect(address)

    def sendto(self, data: bytes, address: Tuple[str, int]) -> int:
        """Send data to a specific address (UDP)."""
        return self._socket.sendto(data, address)

    def recvfrom(self, bufsize: int) -> Tuple[bytes, Tuple[str, int]]:
        """Receive data and sender address (UDP)."""
        return self._socket.recvfrom(bufsize)

    def send(self, data: bytes) -> int:
        """Send data on connected socket."""
        return self._socket.send(data)

    def recv(self, bufsize: int) -> bytes:
        """Receive data from connected socket."""
        return self._socket.recv(bufsize)

    def settimeout(self, timeout: Optional[float]) -> None:
        """Set socket timeout."""
        self._socket.settimeout(timeout)

    def close(self) -> None:
        """Close the socket if not already closed."""
        if not self._closed:
            try:
                self._socket.close()
            except OSError:
                pass
            self._closed = True

    def enable_broadcast(self) -> None:
        """Enable SO_BROADCAST on the socket."""
        self._socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)

    def __enter__(self) -> "ManagedSocket":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
