"""
DNS Protocol Demo Script

Demonstrates the DNS recursive resolver and dynamic cache updates without
the GUI dashboard.
"""

import sys
import os
import time
import socket

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dns_srv.dns_server import DNSServer

def run_dns_demo():
    print("--- DNS Protocol Demo ---")
    
    # Start server
    server = DNSServer(host="127.0.0.1", query_port=5353, update_port=9898)
    server.start(daemon=True)
    time.sleep(1)
    
    print("[*] DNS Server listening on 127.0.0.1:5353")
    
    # 1. Update cache via UDP side-channel
    print("[*] Injecting 'portfolio.local -> 10.0.0.5' via update channel...")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(b"portfolio.local,10.0.0.5", ("127.0.0.1", 9898))
    
    time.sleep(0.5)
    
    # 2. Verify update
    cached = server.cache.lookup("portfolio.local")
    print(f"[+] Cache verification: portfolio.local -> {cached}")
    
    print("\n[*] Demonstration complete. Shutting down...")
    server.shutdown()

if __name__ == "__main__":
    run_dns_demo()
