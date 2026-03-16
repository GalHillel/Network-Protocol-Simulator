"""
Tests for the HTTP/TCP Server implementation.

Tests cover:
    - Server lifecycle (start/shutdown)
    - Client connection handling
    - Invalid request format handling
    - Concurrent client connections
"""

import socket
import threading
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from http_srv.tcp_server import TCPServer
from tests.conftest import find_free_port


class TestTCPServerLifecycle:
    """Test TCP server start/stop behavior."""

    def test_start_and_shutdown(self):
        port = find_free_port()
        server = TCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)
        assert server.is_running
        server.shutdown(timeout=3.0)
        assert not server.is_running

    def test_accepts_connection(self):
        port = find_free_port()
        server = TCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5.0)
                sock.connect(("127.0.0.1", port))
                # Send invalid format to test error handling
                sock.sendall(b"no-comma")
                response = sock.recv(4096).decode("utf-8")
                assert "Error" in response
        finally:
            server.shutdown(timeout=3.0)

    def test_invalid_request_format(self):
        port = find_free_port()
        server = TCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5.0)
                sock.connect(("127.0.0.1", port))
                sock.sendall(b"just-a-url-no-filename")
                response = sock.recv(4096).decode("utf-8")
                assert "Error" in response or "Invalid" in response
        finally:
            server.shutdown(timeout=3.0)

    def test_concurrent_connections(self):
        """Multiple simultaneous clients should all get responses."""
        port = find_free_port()
        server = TCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)

        responses = []
        errors = []

        def client_task(idx: int):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(5.0)
                    sock.connect(("127.0.0.1", port))
                    sock.sendall(f"invalid://url{idx},file{idx}".encode())
                    resp = sock.recv(4096).decode("utf-8")
                    responses.append(resp)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=client_task, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        server.shutdown(timeout=3.0)

        assert not errors
        assert len(responses) == 5
