"""
Reliable UDP (RUDP) Server Implementation

Implements a Stop-and-Wait ARQ reliability layer over UDP, providing:
    - Sequence number tracking with wraparound (0–255)
    - Acknowledgement (ACK) handling
    - Configurable retransmission with exponential backoff
    - Duplicate packet detection
    - Graceful shutdown via BaseServer

Protocol Header Format:
    ┌──────────┬────────┬───────────────────────┐
    │ SEQ (1B) │ FLAGS  │ PAYLOAD (variable)    │
    │          │ (1B)   │                       │
    └──────────┴────────┴───────────────────────┘

Flags:
    0x00 = DATA
    0x01 = ACK
    0x02 = FIN
"""

import socket
import struct
import time
import threading
import mimetypes
from typing import Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path

import requests  # type: ignore[import-untyped]

import sys
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from core.logging_config import setup_logger  # type: ignore
from core.base_server import BaseServer        # type: ignore

logger = setup_logger("rudp.server")

# ── RUDP Protocol Constants ───────────────────────────────────────────

FLAG_DATA = 0x00
FLAG_ACK  = 0x01
FLAG_FIN  = 0x02

HEADER_SIZE = 2          # SEQ (1 byte) + FLAGS (1 byte)
MAX_RETRIES = 5
BASE_TIMEOUT = 1.0       # seconds
MAX_TIMEOUT = 8.0        # seconds (exponential backoff cap)
MAX_PAYLOAD = 1400       # bytes per data packet

# Extend MIME type map
mimetypes.types_map.update({
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".txt": "text/plain",
})


# ── RUDP Packet Utilities ─────────────────────────────────────────────

def make_packet(seq: int, flags: int, payload: bytes = b"") -> bytes:
    """Construct an RUDP packet.

    Args:
        seq: Sequence number (0–255).
        flags: Packet flags (DATA, ACK, FIN).
        payload: Payload data.

    Returns:
        Wire-format bytes: ``[SEQ][FLAGS][PAYLOAD]``.
    """
    return struct.pack("!BB", seq & 0xFF, flags) + payload


def parse_packet(data: bytes) -> Tuple[int, int, bytes]:
    """Parse an RUDP packet.

    Args:
        data: Raw packet bytes.

    Returns:
        Tuple of ``(seq, flags, payload)``.

    Raises:
        ValueError: If packet is too short to contain a valid header.
    """
    if len(data) < HEADER_SIZE:
        raise ValueError(f"Packet too short: {len(data)} bytes")
    seq_flag = struct.unpack_from("!2B", data, 0)
    seq = int(seq_flag[0])
    flags = int(seq_flag[1])
    
    # Use struct for reliable extraction of the remainder
    payload_len = len(data) - HEADER_SIZE
    if payload_len > 0:
        fmt = f"!{payload_len}s"
        payload = struct.unpack_from(fmt, data, HEADER_SIZE)[0]
    else:
        payload = b""
    return seq, flags, payload


# ── File Download ──────────────────────────────────────────────────────

def download_file(url: str, filename: str) -> str:
    """Download a file from *url* and save locally.

    Args:
        url: Source URL.
        filename: Local target filename.

    Returns:
        Status message.
    """
    parsed = urlparse(url)
    if not all([parsed.scheme, parsed.netloc]):
        return "Error: Invalid URL provided"

    try:
        resp = requests.get(url, stream=True, timeout=15)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        final = filename + ext if ext and not filename.endswith(ext) else filename

        total: int = 0
        with open(final, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4096):
                if chunk:
                    b_chunk = bytes(chunk)
                    f.write(b_chunk)
                    total += len(b_chunk)  # type: ignore

        return f"Download complete. File saved as {final} ({total} bytes)."
    except Exception as exc:
        return f"Error: {exc}"


# ── RUDP Server ────────────────────────────────────────────────────────

class RUDPServer(BaseServer):
    """Reliable UDP server using Stop-and-Wait ARQ.

    Receives client requests (``URL,filename``), downloads the file, and
    returns a status message—all with guaranteed delivery via the RUDP
    protocol layer.

    Args:
        host: Bind address (default ``""`` = all interfaces).
        port: UDP port (default ``7878``).
        max_retries: Maximum send retransmissions.
    """

    def __init__(
        self,
        host: str = "",
        port: int = 7878,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        BaseServer.__init__(self, "RUDPServer", host=host, port=port)
        self.max_retries = max_retries
        self._sock: Optional[socket.socket] = None
        self._last_seq: dict[Tuple[str, int], int] = {}  # dedup tracker
        self._ack_events: dict[Tuple[str, int, int], threading.Event] = {}
        self._lock = threading.Lock()

    def _serve_forever(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if sock := self._sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            sock.bind((self.host, self.port))

        logger.info("RUDP Server listening on port %d", self.port)

        while self.is_running:
            try:
                if sock := self._sock:
                    raw, addr = sock.recvfrom(2048)
                    if len(raw) < HEADER_SIZE:
                        continue
                    
                    try:
                        seq, flags, _ = parse_packet(raw)
                    except ValueError:
                        continue

                    if flags == FLAG_ACK:
                        key = (addr[0], addr[1], seq)
                        with self._lock:
                            if event := self._ack_events.get(key):
                                event.set()
                        continue

                    threading.Thread(
                        target=self._handle_request,
                        args=(raw, addr),
                        daemon=True,
                    ).start()
                else:
                    break
            except socket.timeout:
                continue
            except OSError:
                if self.is_running:
                    logger.exception("RUDP socket error")
                break

    def _handle_request(self, raw: bytes, addr: Tuple[str, int]) -> None:
        """Process a single RUDP request from *addr*."""
        try:
            seq, flags, payload = parse_packet(raw)
        except ValueError as exc:
            logger.warning("Malformed packet from %s: %s", addr, exc)
            return

        if flags == FLAG_ACK:
            # Stale ACK — ignore
            return

        logger.info("Received DATA seq=%d from %s (%d bytes)", seq, addr, len(payload))

        # Duplicate detection
        if addr in self._last_seq and self._last_seq[addr] == seq:
            logger.info("Duplicate packet seq=%d from %s — re-ACKing and skipping", seq, addr)
            ack = make_packet(seq, FLAG_ACK)
            self._safe_send(ack, addr)
            return

        self._last_seq[addr] = seq

        # Send ACK for received packet
        ack = make_packet(seq, FLAG_ACK)
        self._safe_send(ack, addr)

        # Process the request
        try:
            text = payload.decode("utf-8")
            parts = text.split(",", maxsplit=1)
            if len(parts) != 2:
                response = 'Error: Invalid format. Use "URL,filename"'
            else:
                url, filename = parts[0].strip(), parts[1].strip()
                response = download_file(url, filename)
        except UnicodeDecodeError:
            response = "Error: Invalid UTF-8 payload"

        # Send response reliably
        resp_seq = (seq + 1) % 256
        resp_packet = make_packet(resp_seq, FLAG_DATA, response.encode("utf-8"))
        self._reliable_send(resp_packet, resp_seq, addr)

    def _safe_send(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Send data with error handling for closed sockets."""
        if not self.is_running:
            return
        if sock := self._sock:
            try:
                sock.sendto(data, addr)
            except OSError as exc:
                if self.is_running:
                    logger.error("Failed to send to %s: %s", addr, exc)

    def _reliable_send(
        self, packet: bytes, seq: int, addr: Tuple[str, int]
    ) -> bool:
        """Send *packet* and wait for ACK, with exponential backoff retries."""
        timeout: float = float(BASE_TIMEOUT)
        for attempt in range(1, self.max_retries + 1):
            self._safe_send(packet, addr)

            # Store event for ACK
            event = threading.Event()
            key = (addr[0], addr[1], seq)
            with self._lock:
                self._ack_events[key] = event

            try:
                if event.wait(timeout=float(timeout)):
                    logger.info("ACK received for seq=%d from %s", seq, addr)
                    return True
            finally:
                with self._lock:
                    self._ack_events.pop(key, None)

            if not self.is_running:
                return False

            logger.warning(
                "Timeout waiting for ACK seq=%d (attempt %d/%d)",
                seq, attempt, self.max_retries,
            )
            timeout = min(float(timeout) * 2.0, float(MAX_TIMEOUT))  # type: ignore

        logger.error("Failed to deliver response seq=%d to %s", seq, addr)
        return False

    def _cleanup(self) -> None:
        sock = self._sock
        if sock:
            try:
                sock.close()
            except OSError:
                pass


# ── Standalone Entry Point ─────────────────────────────────────────────

def main() -> None:
    """Run the RUDP server as a standalone process."""
    server = RUDPServer()
    server.start(daemon=False)
    try:
        server._thread.join()  # type: ignore[union-attr]
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
