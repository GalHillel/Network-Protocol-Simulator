"""
Complete DHCP and DNS Client Example

Simulates a client that first acquires an IP address via DHCP
and then performs a DNS lookup using the newly configured environment.
"""

import socket
import sys
import os
import time

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import dns.message
import dns.query
from core.logging_config import setup_logger

logger = setup_logger("examples.dhcp_dns")

# -- Configuration --------------------------------------------------------

DHCP_SERVER_ADDR = "127.0.0.1"  # Using localhost for simulation
DHCP_SERVER_PORT = 6700          # Matching our refactored server port
DHCP_CLIENT_PORT = 6701

DNS_SERVER_ADDR = "127.0.0.1"
DNS_SERVER_PORT = 5353           # Matching our refactored server port

# -- DHCP Phase -----------------------------------------------------------

def run_dhcp_discover() -> None:
    """Send a DHCP DISCOVER packet and wait for OFFER."""
    logger.info("Starting DHCP Phase...")
    
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2.0)
        sock.bind(("0.0.0.0", DHCP_CLIENT_PORT))

        # Build minimal DISCOVER packet
        xid = b"\x12\x34\x56\x78"
        packet = bytearray(240)
        packet[0] = 0x01 # REQUEST
        packet[1] = 0x01 # Ethernet
        packet[2] = 0x06 # HLEN
        packet[4:8] = xid
        
        # Magic cookie + Option 53 (Discover) + End
        packet += b"\x63\x82\x53\x63" + b"\x35\x01\x01" + b"\xff"

        logger.info("Sending DHCP DISCOVER...")
        sock.sendto(packet, (DHCP_SERVER_ADDR, DHCP_SERVER_PORT))

        try:
            data, addr = sock.recvfrom(1024)
            logger.info("Received response from %s", addr)
            # Check for OFFER (Option 53 = 2)
            if b"\x35\x01\x02" in data:
                assigned_ip = socket.inet_ntoa(data[16:20])
                logger.info("DHCP SUCCESS: Offered IP %s", assigned_ip)
            else:
                logger.warning("Received DHCP response, but not an OFFER.")
        except socket.timeout:
            logger.error("DHCP Discovery timed out. Is the server running?")

# -- DNS Phase ------------------------------------------------------------

def run_dns_query(domain: str) -> None:
    """Perform a DNS query via the local DNS server."""
    logger.info("Starting DNS Phase for '%s'...", domain)
    
    query = dns.message.make_query(domain, "A")
    try:
        response = dns.query.udp(query, DNS_SERVER_ADDR, port=DNS_SERVER_PORT, timeout=2.0)
        if response.answer:
            ip = response.answer[0][0].address
            logger.info("DNS SUCCESS: %s -> %s", domain, ip)
        else:
            logger.warning("DNS query returned no results.")
    except socket.timeout:
        logger.error("DNS query timed out. Is the server running?")
    except Exception as e:
        logger.error("DNS query failed: %s", e)

# -- Main Execution -------------------------------------------------------

def main() -> None:
    """Run full DHCP -> DNS simulation."""
    print("=== Network Protocol Simulator Example ===")
    
    # 1. DHCP
    run_dhcp_discover()
    
    time.sleep(1)
    
    # 2. DNS
    run_dns_query("google.com")
    run_dns_query("localhost")

if __name__ == "__main__":
    main()
