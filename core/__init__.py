"""
Core networking utilities for the Network Protocol Simulator.

Provides shared infrastructure: logging configuration, socket lifecycle
management, network condition simulation, and base server abstractions.
"""

from core.logging_config import setup_logger
from core.socket_manager import ManagedSocket
from core.base_server import BaseServer

__all__ = ["setup_logger", "ManagedSocket", "BaseServer"]
