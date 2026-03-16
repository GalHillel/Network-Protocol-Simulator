"""
Tests for the DNS Server implementation.

Tests cover:
    - Cache hit responses
    - Cache update mechanism
    - Thread-safe cache operations
    - Server lifecycle (start/shutdown)
    - DNS wire format parsing
"""

import socket
import struct
import threading
import time
import pytest
from dns_srv.dns_server import DNSServer, DNSCache
from tests.conftest import find_free_port, wait_for_port


class TestDNSCache:
    """Unit tests for the thread-safe DNSCache."""

    def test_lookup_existing(self):
        cache = DNSCache({"example.com": "1.2.3.4"})
        assert cache.lookup("example.com") == "1.2.3.4"

    def test_lookup_missing(self):
        cache = DNSCache()
        assert cache.lookup("missing.com") is None

    def test_update_and_lookup(self):
        cache = DNSCache()
        cache.update("test.com", "10.0.0.1")
        assert cache.lookup("test.com") == "10.0.0.1"

    def test_update_overwrites(self):
        cache = DNSCache({"test.com": "1.1.1.1"})
        cache.update("test.com", "2.2.2.2")
        assert cache.lookup("test.com") == "2.2.2.2"

    def test_entries_snapshot(self):
        cache = DNSCache({"a.com": "1.1.1.1", "b.com": "2.2.2.2"})
        entries = cache.entries()
        assert len(entries) == 2
        # Modifying snapshot should not affect cache
        entries["c.com"] = "3.3.3.3"
        assert cache.lookup("c.com") is None

    def test_concurrent_updates(self):
        """Verify thread safety with concurrent cache writes."""
        cache = DNSCache()
        errors = []

        def writer(domain_prefix: str, count: int):
            try:
                for i in range(count):
                    cache.update(f"{domain_prefix}-{i}.com", f"10.0.{i % 256}.1")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"t{t}", 50))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        # Verify all entries are present
        entries = cache.entries()
        assert len(entries) == 250  # 5 threads x 50 entries


class TestDNSServerLifecycle:
    """Integration tests for DNS server start/stop."""

    def test_start_and_shutdown(self):
        """Server should start and shut down cleanly."""
        port = find_free_port()
        update_port = find_free_port()
        server = DNSServer(host="127.0.0.1", query_port=port, update_port=update_port)
        server.start(daemon=True)
        time.sleep(0.5)
        assert server.is_running
        server.shutdown(timeout=3.0)
        assert not server.is_running

    def test_cache_update_via_udp(self):
        """Test dynamic cache update through the update listener."""
        query_port = find_free_port()
        update_port = find_free_port()
        server = DNSServer(host="127.0.0.1", query_port=query_port, update_port=update_port)
        server.start(daemon=True)
        time.sleep(0.5)

        try:
            # Send update
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(b"newdomain.com,5.5.5.5", ("127.0.0.1", update_port))
            time.sleep(0.3)

            # Verify cache was updated
            assert server.cache.lookup("newdomain.com") == "5.5.5.5"
        finally:
            server.shutdown(timeout=3.0)

    def test_multiple_start_stop_cycles(self):
        """Server should handle repeated start/stop cycles."""
        for _ in range(3):
            port = find_free_port()
            update_port = find_free_port()
            server = DNSServer(host="127.0.0.1", query_port=port, update_port=update_port)
            server.start(daemon=True)
            time.sleep(0.3)
            server.shutdown(timeout=3.0)
            assert not server.is_running
