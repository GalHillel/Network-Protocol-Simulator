"""
HTTP over TCP Server Implementation

A file-transfer proxy server that downloads files from public URLs and
transmits them back to connected clients over TCP.

Features:
    - Multithreaded client handling
    - Graceful shutdown with socket cleanup
    - Proper MIME type detection
    - Streaming downloads to avoid memory exhaustion
    - BaseServer integration for lifecycle management
"""

import socket
import mimetypes
import sys
import os
import threading
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests  # type: ignore[import-untyped]

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.logging_config import setup_logger  # type: ignore
from core.base_server import BaseServer        # type: ignore

logger = setup_logger("http.tcp_server")

# Ensure common MIME types are registered
mimetypes.types_map.update({
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".zip": "application/zip",
})


def download_file(url: str, filename: str, timeout: float = 30.0) -> str:
    """Download a file from *url* and save it as *filename*.

    Validates the URL, streams the download in chunks to avoid memory
    issues, and appends the correct file extension based on the
    ``Content-Type`` header.

    Args:
        url: Source URL to download.
        filename: Target local filename (extension auto-appended).
        timeout: HTTP request timeout in seconds.

    Returns:
        Status message indicating success or describing the error.
    """
    parsed = urlparse(url)
    if not all([parsed.scheme, parsed.netloc]):
        return "Error: Invalid URL provided"

    try:
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        extension = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""

        if extension and not filename.endswith(extension):
            final_filename = filename + extension
        else:
            final_filename = filename

        total_bytes: int = 0
        with open(final_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    b_chunk: bytes = bytes(chunk)
                    f.write(b_chunk)
                    total_bytes += len(b_chunk)  # type: ignore

        logger.info("Downloaded %d bytes -> %s", total_bytes, final_filename)
        return f"Download complete. File saved as {final_filename} ({total_bytes} bytes)."

    except requests.RequestException as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error writing file: {exc}"


class TCPServer(BaseServer):
    """HTTP file-transfer server over TCP.

    Accepts ``URL,filename`` requests from clients, downloads the file,
    and sends a status response back. Each client connection is handled
    in a separate thread.

    Args:
        host: Interface to bind to (default ``""`` = all interfaces).
        port: TCP port (default ``9898``).
    """

    def __init__(self, host: str = "", port: int = 9898) -> None:
        BaseServer.__init__(self, "TCPServer", host=host, port=port)
        self._server_sock: Optional[socket.socket] = None
        self._active_threads: list[threading.Thread] = []

    def _serve_forever(self) -> None:
        """Accept client connections in a loop."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock = self._server_sock
        assert sock is not None
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))
        sock.listen(10)

        logger.info("TCP HTTP Server listening on port %d", self.port)

        while self.is_running:
            try:
                sock = self._server_sock
                if sock:
                    client_sock, addr = sock.accept()
                    t = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, addr),
                        daemon=True,
                    )
                    t.start()
                    self._active_threads.append(t)
                else:
                    break
            except socket.timeout:
                continue
            except OSError:
                if self.is_running:
                    logger.exception("Accept error")
                break

    def _handle_client(
        self, client_sock: socket.socket, addr: Tuple[str, int]
    ) -> None:
        """Handle a single client connection."""
        logger.info("Connection from %s:%d", *addr)
        try:
            client_sock.settimeout(30.0)
            data = client_sock.recv(2048).decode("utf-8")
            if not data:
                return

            parts = data.split(",", maxsplit=1)
            if len(parts) != 2:
                response = "Error: Invalid format. Use 'URL,filename'"
            else:
                url, filename = parts[0].strip(), parts[1].strip()
                response = download_file(url, filename)

            try:
                client_sock.sendall(response.encode("utf-8"))
            except OSError as exc:
                logger.error("Failed to send response to %s: %s", addr, exc)
        except Exception:
            logger.exception("Error handling client %s:%d", *addr)
        finally:
            client_sock.close()

    def _cleanup(self) -> None:
        """Close the server socket and wait for active threads."""
        sock = self._server_sock
        if sock:
            try:
                sock.close()
            except OSError:
                pass
        for t in self._active_threads:
            t.join(timeout=2.0)


# -- Standalone Entry Point -----------------------------------------------

def main() -> None:
    """Run the TCP HTTP server as a standalone process."""
    server = TCPServer()
    server.start(daemon=False)
    try:
        if server._thread:
            server._thread.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
