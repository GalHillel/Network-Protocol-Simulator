"""
HTTP over TCP Demo Script

Demonstrates the standard multi-threaded TCP server for file transfers.
"""

import sys
import os
import time
import socket
import threading

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from http_srv.tcp_server import TCPServer

def run_http_demo():
    print("--- HTTP over TCP Demo ---")
    
    # Start server on 9898
    server_port = 9898
    server = TCPServer(host="127.0.0.1", port=server_port)
    server.start(daemon=True)
    time.sleep(1)
    
    print(f"[*] HTTP/TCP Server listening on 127.0.0.1:{server_port}")
    
    def client_request():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect(("127.0.0.1", server_port))
                
                # Request the LICENSE file from this repo
                url = "https://raw.githubusercontent.com/GalHillel/Network-Protocol-Simulator/main/LICENSE"
                request = f"{url},demo_license_tcp".encode("utf-8")
                
                print("[*] Client sending TCP request...")
                s.sendall(request)
                
                response = s.recv(4096).decode("utf-8")
                print(f"[+] Server Response: {response}")
        except Exception as e:
            print(f"[!] Client Error: {e}")

    t = threading.Thread(target=client_request)
    t.start()
    t.join(timeout=10)
    
    print("\n[*] Demonstration complete. Shutting down...")
    server.shutdown()

if __name__ == "__main__":
    run_http_demo()
