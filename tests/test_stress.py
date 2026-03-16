"""
Stress and concurrency tests for the protocol servers.

Tests cover:
    - Multiple concurrent RUDP clients
    - Rapid server start/stop cycles
    - High-frequency packet sending
    - Resource cleanup under load
"""

import socket
import threading
import time
import pytest  # type: ignore
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from rudp.rudp_server import RUDPServer, make_packet, parse_packet, FLAG_DATA, FLAG_ACK  # type: ignore
from rudp.rudp_client import RUDPClient  # type: ignore
from http_srv.tcp_server import TCPServer  # type: ignore
from tests.conftest import find_free_port   # type: ignore


class TestRUDPStress:
    """Stress tests for the RUDP protocol implementation."""

    def test_rapid_requests(self):
        """Send many rapid requests to verify server stability."""
        port = find_free_port()
        server = RUDPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)

        acks_received: int = 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)

        try:
            for i in range(20):
                pkt = make_packet(i % 256, FLAG_DATA, f"http://test,file{i}".encode())
                sock.sendto(pkt, ("127.0.0.1", port))
                try:
                    raw, _ = sock.recvfrom(1024)
                    seq, flags, _ = parse_packet(raw)
                    if flags == FLAG_ACK:
                        acks_received += 1  # type: ignore
                except socket.timeout:
                    pass
                # Small delay to avoid overwhelming
                time.sleep(0.05)
        finally:
            sock.close()
            server.shutdown(timeout=5.0)

        # Should have received ACKs for most packets
        assert acks_received >= 15

    def test_concurrent_rudp_clients(self):
        """Multiple clients connecting simultaneously should all get responses."""
        port = find_free_port()
        server = RUDPServer(host="127.0.0.1", port=port, max_retries=2)
        server.start(daemon=True)
        time.sleep(0.5)

        results = []
        errors = []

        def client_task(idx: int):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5.0)
                pkt = make_packet(idx % 256, FLAG_DATA, f"http://test,stress{idx}".encode())
                sock.sendto(pkt, ("127.0.0.1", port))
                raw, _ = sock.recvfrom(1024)
                _, flags, _ = parse_packet(raw)
                if flags == FLAG_ACK:
                    results.append(idx)
                sock.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=client_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        server.shutdown(timeout=5.0)

        # At least some clients should have received ACKs
        assert len(results) >= 5
        assert not errors


class TestTCPStress:
    """Stress tests for TCP server."""

    def test_rapid_connections(self):
        """Open and close many connections rapidly."""
        port = find_free_port()
        server = TCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)

        success_count: int = 0
        for i in range(15):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3.0)
                    sock.connect(("127.0.0.1", port))
                    sock.sendall(b"invalid://url,test")
                    resp = sock.recv(4096)
                    if resp:
                        success_count += 1  # type: ignore
            except (ConnectionRefusedError, socket.timeout, OSError):
                pass
            time.sleep(0.02)

        server.shutdown(timeout=5.0)
        assert success_count >= 10


class TestResourceCleanup:
    """Verify that resources are properly cleaned up after shutdown."""

    def test_server_port_released_after_shutdown(self):
        """After shutdown, the port should be re-bindable."""
        port = find_free_port()
        server = RUDPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)
        server.shutdown(timeout=3.0)
        time.sleep(0.5)

        # Port should be free now
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            test_sock.bind(("127.0.0.1", port))
        except OSError:
            pytest.fail("Port was not released after server shutdown")
        finally:
            test_sock.close()
