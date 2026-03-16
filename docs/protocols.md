# Protocol Implementation Specifications

This document details the wire formats and state machines for the protocols implemented in this simulator.

---

## 🌐 1. DNS (Domain Name System)
Implemented as a recursive resolver over **UDP (Port 5353)**.

### Query Handlers
1.  **UDP Query Listener**: Listens for standard DNS packets. Parses the `Question` section using `dnspython`.
2.  **UDP Update Listener (Internal)**: Custom side-channel for dynamic record injection. Expects `domain,ip` string format.

### Resolution Logic
-   **Cache Hit**: Returns the IP from the thread-safe `DNSCache`.
-   **Cache Miss**: Initiates a recursive lookup to public upstream resolvers (e.g., Google 8.8.8.8).

---

## 📡 2. DHCP (Dynamic Host Configuration Protocol)
Implemented over **UDP (Port 67)** with broadcast capabilities.

### Lease Management
-   **IP Pool**: Managed via `IPPool` class. Supports allocation from `192.168.1.100` to `192.168.1.200`.
-   **Thread Safety**: Uses a `threading.Lock` to ensure ACID-compliant IP assignments.

### DORA Lifecycle
| State | Method | Description |
| :--- | :--- | :--- |
| **Discover** | `_handle_packet` | Client broadcasts request for an advisor. |
| **Offer** | `_send_broadcast` | Server reserves an IP and offers it to the client MAC. |
| **Request** | `_handle_packet` | Client requests the specific offered IP. |
| **Acknowledge** | `_send_broadcast` | Server confirms the lease and commits to cache. |

---

## 🚀 3. RUDP (Reliable UDP)
Custom transport layer providing reliability atop **UDP (Port 7878)**.

### Packet Format
RUDP uses a 2-byte fixed header followed by a variable payload.

| Offset | Field | size | Description |
| :--- | :--- | :--- | :--- |
| 0 | `SEQ` | 1 Byte | Sequence number (0-255) with wraparound. |
| 1 | `FLAGS` | 1 Byte | `0x00` (DATA), `0x01` (ACK), `0x02` (FIN). |
| 2+ | `Payload` | Var | The actual file data or URL string. |

---

## 📄 4. HTTP over TCP
Low-level proxy implementation over **TCP (Port 9898)**.

### Operation
1.  **Connection**: Standard 3-way TCP handshake handled by the OS.
2.  **Request**: Client sends `URL,filename` string.
3.  **Proxying**: Server downloads content from the URL using `requests.get(stream=True)`.
4.  **Transmission**: Streams data back to the client and closes the connection.
