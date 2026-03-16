"""
Network Protocol Benchmark Suite

Measures throughput and latency for the implemented protocols.
"""

import time
import socket
import threading
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rudp.rudp_server import RUDPServer
from rudp.rudp_client import RUDPClient
from http_srv.tcp_server import TCPServer

def benchmark_rudp(port=7878, iterations=5):
    print(f"\n--- Benchmarking RUDP (Reliable UDP) on port {port} ---")
    server = RUDPServer(host="127.0.0.1", port=port)
    server.start(daemon=True)
    time.sleep(1)
    
    url = "https://raw.githubusercontent.com/GalHillel/Network-Protocol-Simulator/main/LICENSE"
    start_time = time.time()
    
    for i in range(iterations):
        with RUDPClient("127.0.0.1", port) as client:
            client.send_request(url, f"bench_rudp_{i}")
            
    end_time = time.time()
    avg_time = (end_time - start_time) / iterations
    print(f"[+] RUDP Average Request Time: {avg_time:.4f}s over {iterations} iterations")
    server.shutdown()

def benchmark_tcp(port=9898, iterations=5):
    print(f"\n--- Benchmarking HTTP over TCP on port {port} ---")
    server = TCPServer(host="127.0.0.1", port=port)
    server.start(daemon=True)
    time.sleep(1)
    
    url = "https://raw.githubusercontent.com/GalHillel/Network-Protocol-Simulator/main/LICENSE"
    start_time = time.time()
    
    for i in range(iterations):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("127.0.0.1", port))
            s.sendall(f"{url},bench_tcp_{i}".encode("utf-8"))
            s.recv(4096)
            
    end_time = time.time()
    avg_time = (end_time - start_time) / iterations
    print(f"[+] TCP Average Request Time: {avg_time:.4f}s over {iterations} iterations")
    server.shutdown()

if __name__ == "__main__":
    benchmark_tcp(iterations=10)
    benchmark_rudp(iterations=10)
