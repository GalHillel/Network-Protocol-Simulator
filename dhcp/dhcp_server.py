"""
DHCP Server Implementation

Simulates a DHCP server implementing the full DORA cycle:
Discover -> Offer -> Request -> Acknowledge.

Features:
    - Thread-safe IP address pool management
    - Proper DHCP option parsing (RFC 2132)
    - Lease tracking with MAC-to-IP assignments
    - Binary packet construction using ``struct``
    - Graceful shutdown support
"""

import socket
import struct
import sys
import os
import threading
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.logging_config import setup_logger  # type: ignore[import-not-found, import-untyped]
from core.base_server import BaseServer        # type: ignore[import-not-found, import-untyped]

logger = setup_logger("dhcp.server")

# DHCP Magic Cookie (RFC 2131)
DHCP_MAGIC_COOKIE = b"\x63\x82\x53\x63"

# DHCP Message Types (Option 53)
DHCP_DISCOVER = 1
DHCP_OFFER = 2
DHCP_REQUEST = 3
DHCP_DECLINE = 4
DHCP_ACK = 5
DHCP_NAK = 6
DHCP_RELEASE = 7


class IPPool:
    """Thread-safe IP address pool manager.

    Tracks available and assigned addresses within a configured subnet range.
    """

    def __init__(self, subnet: str = "192.168.1", start: int = 100, end: int = 200) -> None:
        self._lock = threading.Lock()
        self._available: List[str] = [f"{subnet}.{i}" for i in range(start, end + 1)]
        self._assigned: Dict[bytes, str] = {}  # MAC -> IP

    def allocate(self, mac: bytes) -> Optional[str]:
        """Allocate an IP address for the given MAC.

        If the MAC already has a lease, return the existing assignment.
        Otherwise, assign the next available address from the pool.

        Args:
            mac: 6-byte hardware address.

        Returns:
            The assigned IP string, or ``None`` if the pool is exhausted.
        """
        with self._lock:
            # Return existing lease
            if mac in self._assigned:
                return self._assigned[mac]
            # Assign new
            if not self._available:
                return None
            ip = self._available.pop(0)
            self._assigned[mac] = ip
            return ip

    def release(self, mac: bytes) -> Optional[str]:
        """Release the IP assigned to *mac* back to the pool."""
        with self._lock:
            ip = self._assigned.pop(mac, None)
            if ip:
                self._available.append(ip)
            return ip

    @property
    def stats(self) -> Dict[str, int]:
        """Return pool utilization stats."""
        with self._lock:
            return {
                "available": len(self._available),
                "assigned": len(self._assigned),
            }


class DHCPServer(BaseServer):
    """DHCP Server implementing the DORA (Discover/Offer/Request/ACK) cycle.

    Manages an IP address pool and responds to broadcast DHCP messages
    from clients on the local subnet.

    Args:
        host: Interface to bind to (default ``"0.0.0.0"``).
        port: UDP port (default ``6700`` to avoid requiring root for port 67).
        lease_time: Lease duration in seconds (default ``3600``).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6700,
        lease_time: int = 3600,
    ) -> None:
        BaseServer.__init__(self, "DHCPServer", host=host, port=port)
        self.lease_time = lease_time
        self.pool = IPPool()
        self._sock: Optional[socket.socket] = None

    # -- Lifecycle -------------------------------------------------------

    def _serve_forever(self) -> None:
        """Main DHCP receive loop."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))
        self._sock = sock

        logger.info("DHCP Server listening on %s:%d", self.host, self.port)

        while self.is_running:
            try:
                data, addr = sock.recvfrom(1024)
                if len(data) < 240:
                    continue
                self._handle_packet(data, addr)
            except socket.timeout:
                continue
            except OSError:
                if self.is_running:
                    logger.exception("DHCP socket error")
                break

    def _cleanup(self) -> None:
        if sock := self._sock:
            try:
                sock.close()
            except OSError:
                pass

    # -- Packet Handling -------------------------------------------------

    def _handle_packet(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Dispatch a DHCP packet based on its message type option."""
        if len(data) < 34:
            return
            
        # Use struct for reliable extraction for analyzers
        xid = struct.unpack_from("!4s", data, 4)[0]
        mac = struct.unpack_from("!6s", data, 28)[0]
        msg_type = self._extract_message_type(data)

        if msg_type is None:
            logger.warning("Received DHCP packet without message type from %s", addr)
            return

        mac_str = mac.hex(":")

        if msg_type == DHCP_DISCOVER:
            logger.info("DISCOVER from %s", mac_str)
            ip = self.pool.allocate(mac)
            if ip:
                offer = self._build_response(xid, ip, DHCP_OFFER)
                self._send_broadcast(offer)
                logger.info("OFFER %s to %s", ip, mac_str)
            else:
                logger.warning("IP pool exhausted - cannot offer to %s", mac_str)

        elif msg_type == DHCP_REQUEST:
            logger.info("REQUEST from %s", mac_str)
            ip = self.pool.allocate(mac)
            if ip:
                ack = self._build_response(xid, ip, DHCP_ACK)
                self._send_broadcast(ack)
                logger.info("ACK %s to %s", ip, mac_str)
            else:
                nak = self._build_response(xid, "0.0.0.0", DHCP_NAK)
                self._send_broadcast(nak)
                logger.warning("NAK to %s - pool exhausted", mac_str)

        elif msg_type == DHCP_RELEASE:
            released = self.pool.release(mac)
            if released:
                logger.info("RELEASE %s from %s", released, mac_str)

    def _send_broadcast(self, packet: bytes) -> None:
        """Send a DHCP response as a broadcast."""
        sock = self._sock
        if not sock:
            return

        try:
            sock.sendto(packet, ("<broadcast>", self.port + 1))
        except OSError as exc:
            # Fallback to localhost if broadcast fails
            logger.debug("Broadcast failed (%s), sending to localhost", exc)
            try:
                sock.sendto(packet, ("127.0.0.1", self.port + 1))
            except OSError:
                logger.error("Failed to send even to localhost")

    # -- Packet Construction ---------------------------------------------

    def _build_response(self, xid: bytes, ip: str, msg_type: int) -> bytes:
        """Construct a DHCP response packet.

        Args:
            xid: 4-byte transaction ID from the client request.
            ip: IP address to include in ``yiaddr``.
            msg_type: DHCP message type (OFFER=2, ACK=5, NAK=6).

        Returns:
            The complete DHCP response as bytes.
        """
        packet = bytearray(240)
        packet[0] = 0x02  # BOOTREPLY
        packet[1] = 0x01  # Ethernet
        packet[2] = 0x06  # HLEN = 6

        struct.pack_into("!4s", packet, 4, xid)
        struct.pack_into("!4s", packet, 16, socket.inet_aton(ip))

        server_ip = self.host if self.host != "0.0.0.0" else "127.0.0.1"
        struct.pack_into("!4s", packet, 20, socket.inet_aton(server_ip))

        # DHCP Options
        packet += DHCP_MAGIC_COOKIE
        # Option 53: DHCP Message Type
        packet += bytes([53, 1, msg_type])
        # Option 51: Lease Time
        packet += b"\x33\x04" + struct.pack("!I", self.lease_time)
        # Option 54: Server Identifier
        packet += b"\x36\x04" + socket.inet_aton(server_ip)
        # Option 1: Subnet Mask
        packet += b"\x01\x04" + socket.inet_aton("255.255.255.0")
        # End
        packet += b"\xff"

        return bytes(packet)

    @staticmethod
    def _extract_message_type(data: bytes) -> Optional[int]:
        """Extract DHCP message type (Option 53) from the options field.

        Args:
            data: Full DHCP packet as bytes.

        Returns:
            The message type integer, or ``None`` if not found.
        """
        if len(data) < 244:
            return None

        # Use struct for reliable extraction for analyzers
        cookie = struct.unpack_from("!4s", data, 240)[0]
        if cookie != DHCP_MAGIC_COOKIE:
            return None

        offset = 244
        while offset < len(data):
            opt = struct.unpack_from("!B", data, offset)[0]
            if opt == 0xFF:
                break
            if opt == 0x00:
                offset += 1
                continue
            if offset + 1 >= len(data):
                break
            length = struct.unpack_from("!B", data, offset + 1)[0]
            if opt == 53 and length >= 1 and offset + 2 < len(data):
                return struct.unpack_from("!B", data, offset + 2)[0]
            offset += 2 + length

        return None


# -- Standalone Entry Point -----------------------------------------------

def main() -> None:
    """Run the DHCP server as a standalone process."""
    server = DHCPServer()
    server.start(daemon=False)
    try:
        server._thread.join()  # type: ignore[union-attr]
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
