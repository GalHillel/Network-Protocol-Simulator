"""
DNS Server Implementation

A recursive DNS resolver with local caching and dynamic record updates.
Features thread-safe cache, graceful shutdown, and structured logging.

Architecture:
    - Query Listener (UDP port 5353): Handles standard DNS A-record queries
    - Update Listener (UDP port 9898): Accepts dynamic record updates via
      a simple ``domain,ip`` text protocol

Cache Strategy:
    1. Check local thread-safe cache
    2. On miss, perform recursive upstream lookup via ``dnspython``
    3. Cache results for subsequent queries
"""

import socket
import struct
import sys
import os
import threading
from typing import Dict, Optional, Tuple

# Ensure project root is on path for core imports
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import dns.message    # type: ignore[import-not-found, import-untyped]
import dns.name       # type: ignore[import-not-found, import-untyped]
import dns.rcode      # type: ignore[import-not-found, import-untyped]
import dns.resolver   # type: ignore[import-not-found, import-untyped]
import dns.rrset      # type: ignore[import-not-found, import-untyped]

from core.logging_config import setup_logger  # type: ignore
from core.base_server import BaseServer        # type: ignore

logger = setup_logger("dns.server")


class DNSCache:
    """Thread-safe DNS record cache.

    Stores ``domain -> IP`` mappings and provides atomic read/write access
    using an internal ``threading.Lock``.
    """

    def __init__(self, initial: Optional[Dict[str, str]] = None) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, str] = dict(initial) if initial else {}

    def lookup(self, domain: str) -> Optional[str]:
        """Return the cached IP for *domain*, or ``None`` if not cached."""
        with self._lock:
            return self._records.get(domain)

    def update(self, domain: str, ip: str) -> None:
        """Insert or update a record in the cache."""
        with self._lock:
            self._records[domain] = ip
        logger.info("Cache updated: %s -> %s", domain, ip)

    def entries(self) -> Dict[str, str]:
        """Return a snapshot of all cached records."""
        with self._lock:
            return dict(self._records)


class DNSServer(BaseServer):
    """DNS Recursive Resolver with local caching.

    Runs two UDP listeners:
        * **Query listener** on ``query_port`` - resolves DNS ``A`` queries
        * **Update listener** on ``update_port`` - accepts ``domain,ip``
          text updates for cache injection

    Args:
        host: Interface to bind to (default ``"0.0.0.0"``).
        query_port: Port for DNS queries (default ``5353``).
        update_port: Port for cache updates (default ``9898``).
    """

    DEFAULT_CACHE = {
        "google.com": "8.8.8.8",
        "yahoo.com": "98.138.219.232",
        "localhost": "127.0.0.1",
    }

    def __init__(
        self,
        host: str = "0.0.0.0",
        query_port: int = 5353,
        update_port: int = 9898,
    ) -> None:
        BaseServer.__init__(self, "DNSServer", host=host, port=query_port)
        self.query_port = query_port
        self.update_port = update_port
        self.cache = DNSCache(self.DEFAULT_CACHE.copy())
        self._query_sock: Optional[socket.socket] = None
        self._update_sock: Optional[socket.socket] = None

    # -- Lifecycle -------------------------------------------------------

    def _serve_forever(self) -> None:
        """Start both query and update listeners in separate threads."""
        # Instantiate sockets
        self._query_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._update_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Start listeners
        q_sock = self._query_sock
        if q_sock:
            q_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            q_sock.settimeout(1.0)
            q_sock.bind((self.host, self.query_port))

        u_sock = self._update_sock
        if u_sock:
            u_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            u_sock.settimeout(1.0)
            u_sock.bind((self.host, self.update_port))

        update_thread = threading.Thread(
            target=self._listen_updates,
            name="DNSUpdate-thread",
            daemon=True,
        )
        update_thread.start()

        logger.info(
            "DNS query listener on port %d, update listener on port %d",
            self.query_port,
            self.update_port,
        )
        self._listen_queries()
        return None

    def _cleanup(self) -> None:
        """Close both UDP sockets."""
        for sock in (self._query_sock, self._update_sock):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    # -- Query Handling --------------------------------------------------

    def _listen_queries(self) -> None:
        """Main query receive loop."""
        while self.is_running:
            try:
                sock = self._query_sock
                if sock:
                    data, addr = sock.recvfrom(512)
                    self._handle_query(data, addr, sock)
                else:
                    break
            except socket.timeout:
                continue
            except OSError:
                if self.is_running:
                    logger.exception("Query listener socket error")
                break
            except Exception:
                break

    def _handle_query(
        self, query_data: bytes, client_addr: Tuple[str, int], sock: socket.socket
    ) -> None:
        """Parse a DNS wire-format query and send an appropriate response."""
        try:
            message = dns.message.from_wire(query_data)
            if not message.question:
                return

            q_name = message.question[0].name
            domain = q_name.to_text().strip(".")
            logger.info("Query for '%s' from %s", domain, client_addr)

            # 1. Cache hit
            cached_ip = self.cache.lookup(domain)
            if cached_ip:
                response = dns.message.make_response(message)
                response.answer.append(
                    dns.rrset.from_text(q_name, 300, "IN", "A", cached_ip)
                )
                sock.sendto(response.to_wire(), client_addr)
                logger.info("Cache HIT: %s -> %s", domain, cached_ip)
                return

            # 2. Recursive upstream lookup
            try:
                resolver = dns.resolver.Resolver()
                answer = resolver.resolve(domain, "A")
                sock.sendto(answer.response.to_wire(), client_addr)
                logger.info("Recursive lookup OK: %s", domain)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                response = dns.message.make_response(message)
                response.set_rcode(dns.rcode.NXDOMAIN)
                sock.sendto(response.to_wire(), client_addr)
                logger.warning("NXDOMAIN: %s", domain)
            except Exception:
                logger.exception("Upstream resolver error for %s", domain)

        except Exception:
            logger.exception("DNS query handling error from %s", client_addr)

    # -- Update Handling -------------------------------------------------

    def _listen_updates(self) -> None:
        """Receive ``domain,ip`` text updates and inject into cache."""
        while self.is_running:
            try:
                sock = self._update_sock
                if sock:
                    data, addr = sock.recvfrom(512)
                    msg = data.decode("utf-8").strip()
                    parts = msg.split(",")
                    if len(parts) == 2:
                        domain, ip = parts[0].strip(), parts[1].strip()
                        self.cache.update(domain, ip)
                    else:
                        logger.warning("Invalid update from %s: %r", addr, msg)
                else:
                    break
            except socket.timeout:
                continue
            except OSError:
                if self.is_running:
                    logger.exception("Update listener socket error")
                break
            except Exception:
                logger.exception("Error processing DNS update")
        return None


# -- Standalone Entry Point -----------------------------------------------

def main() -> None:
    """Run the DNS server as a standalone process."""
    server = DNSServer()
    server.start(daemon=False)
    try:
        server._thread.join()  # type: ignore[union-attr]
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
