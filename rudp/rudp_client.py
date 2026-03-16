"""
Reliable UDP (RUDP) Client Implementation

Communicates with the RUDP server using Stop-and-Wait ARQ with:
    - Sequence number tracking
    - ACK verification
    - Configurable retransmission with exponential backoff
    - Timeout handling

Protocol Header Format:
    ┌──────────┬────────┬───────────────────────┐
    │ SEQ (1B) │ FLAGS  │ PAYLOAD (variable)    │
    │          │ (1B)   │                       │
    └──────────┴────────┴───────────────────────┘
"""

import socket
import struct
import time
from typing import Optional, Tuple

import sys
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from core.logging_config import setup_logger  # type: ignore[import-not-found, import-untyped]

logger = setup_logger("rudp.client")

# Import shared protocol constants
FLAG_DATA = 0x00
FLAG_ACK  = 0x01
FLAG_FIN  = 0x02
HEADER_SIZE = 2

MAX_RETRIES = 5
BASE_TIMEOUT = 2.0
MAX_TIMEOUT = 16.0
RESPONSE_TIMEOUT = 30.0


def make_packet(seq: int, flags: int, payload: bytes = b"") -> bytes:
    """Construct an RUDP packet."""
    return struct.pack("!BB", seq & 0xFF, flags) + payload


def parse_packet(data: bytes) -> Tuple[int, int, bytes]:
    """Parse an RUDP packet into (seq, flags, payload)."""
    if len(data) < HEADER_SIZE:
        raise ValueError(f"Packet too short: {len(data)} bytes")
    seq_flag = struct.unpack("!2B", data[:HEADER_SIZE])  # type: ignore[index]
    seq = int(seq_flag[0])
    flags = int(seq_flag[1])
    return seq, flags, data[HEADER_SIZE:]  # type: ignore[index]


class RUDPClient:
    """Reliable UDP client using Stop-and-Wait ARQ.

    Sends requests to an RUDP server and reliably receives responses.

    Args:
        host: Server hostname or IP.
        port: Server port (default ``7878``).
        max_retries: Maximum retransmission attempts per packet.

    Example::

        client = RUDPClient("localhost", 7878)
        response = client.send_request("https://example.com/file.pdf", "output")
        print(response)
        client.close()
    """

    def __init__(
        self,
        host: str,
        port: int = 7878,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq: int = 0

    @property
    def server_address(self) -> Tuple[str, int]:
        """Return the server (host, port) tuple."""
        return (self.host, self.port)

    def send_request(self, url: str, filename: str) -> str:
        """Send a download request and wait for the server's response.

        Uses two-phase reliable delivery:
            1. Send the request and wait for ACK
            2. Wait for the server's response and ACK it

        Args:
            url: Source URL for the server to download.
            filename: Target filename on the server side.

        Returns:
            The server's response message, or an error string.
        """
        payload = f"{url},{filename}".encode("utf-8")
        packet = make_packet(self._seq, FLAG_DATA, payload)

        # ── Phase 1: Send request with reliable delivery ──
        if not self._reliable_send(packet, self._seq):
            return "Error: Server failed to acknowledge request."

        # ── Phase 2: Wait for server response ──
        try:
            if sock := self._sock:
                sock.settimeout(RESPONSE_TIMEOUT)
                expected_seq = (self._seq + 1) % 256

                deadline = time.monotonic() + float(RESPONSE_TIMEOUT)  # type: ignore[operator]
                while time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()  # type: ignore[operator]
                    if remaining <= 0:
                        break

                    sock.settimeout(max(0.1, remaining))
                    try:
                        raw, _ = sock.recvfrom(2048)
                    except socket.timeout:
                        break

                    try:
                        seq, flags, resp_payload = parse_packet(raw)
                    except ValueError:
                        continue

                    if flags == FLAG_ACK:
                        # Late ACK for our request — ignore
                        continue

                    if flags == FLAG_DATA and seq == expected_seq:
                        # Send ACK for server response
                        ack = make_packet(seq, FLAG_ACK)
                        sock.sendto(ack, self.server_address)

                        self._seq = (seq + 1) % 256
                        return resp_payload.decode("utf-8")

                return "Error: Timed out waiting for server response."
            else:
                return "Error: Socket not available."

        except socket.timeout:
            return "Error: Timed out waiting for server response."
        except Exception as exc:
            return f"Error: {exc}"
        finally:
            if sock := self._sock:
                try:
                    sock.settimeout(BASE_TIMEOUT)
                except OSError:
                    pass
        
        return "Error: Unexpected termination of request handler."

    def _reliable_send(self, packet: bytes, seq: int) -> bool:
        """Send *packet* and wait for ACK with exponential backoff.

        Returns:
            ``True`` if ACK received, ``False`` if retries exhausted.
        """
        timeout: float = float(BASE_TIMEOUT)
        for attempt in range(1, self.max_retries + 1):
            logger.info("Sending seq=%d (attempt %d/%d)", seq, attempt, self.max_retries)
            if sock := self._sock:
                sock.sendto(packet, self.server_address)

                deadline = time.monotonic() + float(timeout)  # type: ignore[operator]
                while time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()  # type: ignore[operator]
                    if remaining <= 0:
                        break
                    try:
                        sock.settimeout(max(0.1, remaining))
                        raw, _ = sock.recvfrom(1024)
                        ack_seq, ack_flags, _ = parse_packet(raw)
                        if ack_flags == FLAG_ACK and ack_seq == seq:
                            logger.info("ACK received for seq=%d", seq)
                            return True
                    except (socket.timeout, ValueError):
                        continue

            logger.warning("Timeout for ACK seq=%d (attempt %d)", seq, attempt)
            timeout = min(float(timeout) * 2.0, float(MAX_TIMEOUT))  # type: ignore

        return False

    def close(self) -> None:
        """Close the client socket."""
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "RUDPClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# ── Standalone Entry Point ─────────────────────────────────────────────

def main() -> None:
    """Simple CLI demo of the RUDP client."""
    host = "localhost"
    port = 7878
    url = "https://www.africau.edu/images/default/sample.pdf"
    filename = "test_download"

    logger.info("Connecting to RUDP server at %s:%d", host, port)

    with RUDPClient(host, port) as client:
        response = client.send_request(url, filename)
        logger.info("Server response: %s", response)


if __name__ == "__main__":
    main()
