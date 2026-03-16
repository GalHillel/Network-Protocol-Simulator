"""
RUDP Reliability Demo Script

Demonstrates file transfer over the custom RUDP protocol with automatic
acknowledgments and timeout handling.
"""

import sys
import os
import time
import threading

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rudp.rudp_server import RUDPServer
from rudp.rudp_client import RUDPClient

def run_rudp_demo():
    print("--- RUDP Protocol Demo ---")
    
    # Start server
    server_port = 7878
    server = RUDPServer(host="127.0.0.1", port=server_port)
    server.start(daemon=True)
    time.sleep(1)
    
    print(f"[*] RUDP Server listening on 127.0.0.1:{server_port}")
    
    # Run client request in a separate thread context
    def client_task():
        try:
            with RUDPClient("127.0.0.1", server_port) as client:
                print("[*] Client requesting file download via RUDP...")
                # We use a known public asset (text file)
                url = "https://raw.githubusercontent.com/GalHillel/Network-Protocol-Simulator/main/LICENSE"
                response = client.send_request(url, "demo_license_rudp")
                print(f"[+] Server Response: {response}")
        except Exception as e:
            print(f"[!] Client Error: {e}")

    t = threading.Thread(target=client_task)
    t.start()
    t.join(timeout=15)
    
    print("\n[*] Demonstration complete. Shutting down...")
    server.shutdown()

if __name__ == "__main__":
    run_rudp_demo()
