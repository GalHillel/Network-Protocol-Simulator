"""
Tests for the DHCP Server implementation.

Tests cover:
    - IP pool allocation and release
    - Pool exhaustion handling
    - Thread-safe pool operations
    - DHCP packet construction and parsing
    - Server lifecycle
"""

import socket
import struct
import threading
import time
import pytest
from dhcp.dhcp_server import DHCPServer, IPPool, DHCP_MAGIC_COOKIE, DHCP_DISCOVER, DHCP_REQUEST
from tests.conftest import find_free_port


class TestIPPool:
    """Unit tests for the thread-safe IP address pool."""

    def test_allocate_new(self):
        pool = IPPool(start=100, end=102)
        mac = b"\x00\x01\x02\x03\x04\x05"
        ip = pool.allocate(mac)
        assert ip == "192.168.1.100"

    def test_allocate_returns_existing_lease(self):
        pool = IPPool(start=100, end=102)
        mac = b"\x00\x01\x02\x03\x04\x05"
        ip1 = pool.allocate(mac)
        ip2 = pool.allocate(mac)
        assert ip1 == ip2

    def test_allocate_different_macs(self):
        pool = IPPool(start=100, end=102)
        mac1 = b"\x01\x02\x03\x04\x05\x06"
        mac2 = b"\x06\x05\x04\x03\x02\x01"
        ip1 = pool.allocate(mac1)
        ip2 = pool.allocate(mac2)
        assert ip1 != ip2

    def test_pool_exhaustion(self):
        pool = IPPool(start=100, end=101)  # Only 2 IPs
        pool.allocate(b"\x01" * 6)
        pool.allocate(b"\x02" * 6)
        result = pool.allocate(b"\x03" * 6)
        assert result is None

    def test_release_and_reallocate(self):
        pool = IPPool(start=100, end=100)  # Only 1 IP
        mac1 = b"\x01" * 6
        mac2 = b"\x02" * 6
        ip1 = pool.allocate(mac1)
        assert ip1 is not None

        # Pool should be exhausted
        assert pool.allocate(mac2) is None

        # Release and reallocate
        pool.release(mac1)
        ip2 = pool.allocate(mac2)
        assert ip2 is not None

    def test_stats(self):
        pool = IPPool(start=100, end=104)
        pool.allocate(b"\x01" * 6)
        pool.allocate(b"\x02" * 6)
        stats = pool.stats
        assert stats["assigned"] == 2
        assert stats["available"] == 3

    def test_concurrent_allocation(self):
        """Verify thread-safe allocation under concurrent pressure."""
        pool = IPPool(start=1, end=100)
        allocated = []
        lock = threading.Lock()
        errors = []

        def allocator(start_idx: int):
            try:
                for i in range(20):
                    mac = bytes([start_idx, i, 0, 0, 0, 0])
                    ip = pool.allocate(mac)
                    if ip:
                        with lock:
                            allocated.append(ip)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=allocator, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert len(allocated) == 100
        # All IPs should be unique
        assert len(set(allocated)) == 100


class TestDHCPPacketConstruction:
    """Test DHCP packet building and parsing."""

    def test_extract_message_type_discover(self):
        """Build a minimal DISCOVER packet and verify option parsing."""
        packet = bytearray(240)
        packet[0] = 0x01  # BOOTREQUEST
        # Append magic cookie + option 53 (discover)
        packet += DHCP_MAGIC_COOKIE
        packet += bytes([53, 1, DHCP_DISCOVER])
        packet += b"\xff"

        msg_type = DHCPServer._extract_message_type(packet)
        assert msg_type == DHCP_DISCOVER

    def test_extract_message_type_request(self):
        packet = bytearray(240)
        packet += DHCP_MAGIC_COOKIE
        packet += bytes([53, 1, DHCP_REQUEST])
        packet += b"\xff"

        msg_type = DHCPServer._extract_message_type(packet)
        assert msg_type == DHCP_REQUEST

    def test_extract_message_type_missing(self):
        """Packet without option 53 should return None."""
        packet = bytearray(240)
        packet += DHCP_MAGIC_COOKIE
        packet += b"\xff"

        msg_type = DHCPServer._extract_message_type(packet)
        assert msg_type is None

    def test_build_response_offer(self):
        xid = b"\x01\x02\x03\x04"
        server = DHCPServer(port=find_free_port())
        response = server._build_response(xid, "192.168.1.100", 2)

        # Verify BOOTREPLY
        assert response[0] == 0x02
        # Verify XID
        assert response[4:8] == xid
        # Verify yiaddr
        assert socket.inet_ntoa(response[16:20]) == "192.168.1.100"


class TestDHCPServerLifecycle:
    """Integration tests for DHCP server."""

    def test_start_and_shutdown(self):
        port = find_free_port()
        server = DHCPServer(host="127.0.0.1", port=port)
        server.start(daemon=True)
        time.sleep(0.5)
        assert server.is_running
        server.shutdown(timeout=3.0)
        assert not server.is_running
