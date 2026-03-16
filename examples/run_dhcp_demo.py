"""
DHCP DORA Demo Script

Demonstrates the DHCP Discover-Offer-Request-Ack lifecycle using
the custom DHCPServer and IPPool management.
"""

import sys
import os
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dhcp.dhcp_server import DHCPServer

def run_dhcp_demo():
    print("--- DHCP Infrastructure Demo ---")
    
    # Start server
    server = DHCPServer(host="127.0.0.1", port=6767) # Use non-standard port for demo
    server.start(daemon=True)
    time.sleep(1)
    
    pool_stats = server.pool.get_stats()
    print(f"[*] DHCP Server active. Pool size: {pool_stats['total_ips']} IPs.")
    print(f"[*] IP Range: {server.pool.start_ip} - {server.pool.end_ip}")
    
    # Simulate a client MAC allocation
    test_mac = b"\xde\xad\xbe\xef\xca\xfe"
    print(f"[*] Simulating allocation for MAC: {test_mac.hex(':')}")
    
    offered_ip = server.pool.allocate(test_mac)
    print(f"[+] Pool allocated IP: {offered_ip}")
    
    # Verify lease
    stats_after = server.pool.get_stats()
    print(f"[+] Active leases: {stats_after['active_leases']}")
    
    print("\n[*] Demonstration complete. Shutting down...")
    server.shutdown()

if __name__ == "__main__":
    run_dhcp_demo()
