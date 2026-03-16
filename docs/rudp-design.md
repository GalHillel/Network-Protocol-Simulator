# RUDP: Reliable UDP Design Specification

Reliable UDP (RUDP) in this project is a custom transport layer implementation designed to solve the inherent packet loss and reordering issues of standard UDP while maintaining lower overhead than full TCP.

---

## ⚙️ Design Philosophy: Stop-and-Wait ARQ

The protocol implements the **Stop-and-Wait Automatic Repeat Request (ARQ)** pattern. This ensures simplicity and correctness in high-latency or high-loss environments.

### 🔄 The Delivery Loop
1.  **Sender**: Transmits a DATA packet with sequence $N$. Starts a timer.
2.  **Sender**: Blocks and waits for an ACK packet with sequence $N$.
3.  **Receiver**: Receives DATA($N$). If it's a new packet, it processes the payload.
4.  **Receiver**: Responds with ACK($N$).
5.  **Sender**: Receives ACK($N$), increments sequence to $N+1$, and proceeds to the next chunk.

---

## 🛡 Reliability Mechanisms

### 1. Cumulative Acknowledgments
Every DATA packet must be acknowledged. If the sender does not receive an ACK within the `BASE_TIMEOUT` (1.0s), it assumes the packet was lost and initiates a retransmission.

### 2. Exponential Backoff
To prevent network congestion (simulating a "Polite" protocol), RUDP doubles its timeout after every failed attempt:
-   Attempt 1: 1.0s
-   Attempt 2: 2.0s
-   Attempt 3: 4.0s
-   Attempt 4: 8.0s (Max Cap)

### 3. Sequence Wraparound & Deduping
With a 1-byte sequence field, numbers range from `0` to `255`. The server maintains a `_last_seq` mapping for every client (IP, Port) to detect and discard duplicate packets caused by delayed ACKs or network echoes.

---

## 📊 Performance Characteristics

### Overhead Analysis
Compared to TCP's 20-byte header, RUDP uses only **2 bytes**, resulting in significantly lower header overhead for small payloads.

| Metric | RUDP Implementation |
| :--- | :--- |
| **Header Size** | 2 Bytes |
| **Max Payload** | 1400 Bytes (to stay under MTU) |
| **Max Retries** | 5 Attempts |
| **Flow Control** | Stop-and-Wait (Single packet window) |

### Use Case
The RUDP implementation is ideal for the simulated "Command and Control" or "Large File Transfer" scenarios where guaranteed delivery is critical, but the overhead of a windowing system (like Selective Repeat) is not required for the demonstration.
