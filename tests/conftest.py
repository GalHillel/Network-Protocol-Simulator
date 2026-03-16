"""
Shared test fixtures and configuration for the protocol test suite.
"""

import socket
import threading
import time
import pytest
from typing import Generator


def find_free_port() -> int:
    """Find and return a free TCP/UDP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 5.0) -> bool:
    """Wait until a UDP port is bound and ready.

    For UDP we just try a simple check by attempting to bind — if it fails,
    the port is in use (i.e., the server is running).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind((host, port))
            # If bind succeeds, port is free — server not ready yet
            time.sleep(0.1)
        except OSError:
            return True
    return False
