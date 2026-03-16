# Wireshark Traffic Analysis Guide

This project is designed to be validated using **Wireshark**. You can inspect the binary accuracy of our protocol implementations by capturing traffic on the loopback interface (`127.0.0.1`).

---

## 🔍 How to Analyze Simulation Traffic

### 1. Setup Capture
-   Open Wireshark.
-   Select the **Adapter for loopback traffic** (on Windows, this may require Npcap).
-   Set a display filter to view only simulator traffic:
    ```text
    udp.port == 5353 || udp.port == 67 || tcp.port == 9898 || udp.port == 7878
    ```

### 2. DNS Analysis (Port 5353)
Our DNS implementation uses standard wire formats. You can expand the `Domain Name System` tree in Wireshark to see:
-   **Transaction IDs**: Should match between Query and Response.
-   **Flags**: Check for `Recursion Desired`.
-   **Queries**: Verify the domain name string parsing.

### 3. DHCP Analysis (Port 67/68)
DHCP packets are large and feature many options. Look for:
-   **Message Type 53**: Identifies Discover, Offer, Request, or Ack.
-   **Magic Cookie**: `0x63825363` must be present at the start of the options field.
-   **Option 54**: Server Identifier (check for our simulated IP).

### 4. RUDP Analysis (Port 7878)
Since RUDP is a custom protocol, Wireshark will label it as "UDP". You will need to inspect the **Data** payload:
-   The first byte is the **Sequence Number**.
-   The second byte is the **Flags** (`00` for Data, `01` for ACK).
-   Observe the timing between a DATA packet and its corresponding ACK to visualize the Stop-and-Wait mechanism.

---

## 📁 Pre-recorded Captures
Samples of successful handshakes are located in the `analysis/` directory.

-   `dns_recursive_lookup.pcapng`: Shows a cache miss followed by an upstream resolution.
-   `dhcp_full_dora.pcapng`: The complete 4-packet negotiation for an IP lease.
-   `rudp_file_transfer.pcapng`: Exhibits a long sequence of DATA/ACK pairs for a 50KB file.
