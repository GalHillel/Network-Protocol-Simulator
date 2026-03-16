import socket
import dns.resolver
import random
import time
import string

# DHCP settings
dhcp_server_address = "0.0.0.0"
dhcp_server_port = 67

# DNS settings
dns_server_address = "127.0.0.1"
dns_server_port = 533

# Create a DHCP socket and send a DHCP discover message
dhcp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dhcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
dhcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
dhcp_socket.bind(("0.0.0.0", 68))


def generate_transaction_id():
    transaction_id = b''
    for i in range(4):
        transaction_id += bytes([random.randint(0, 255)])
    return transaction_id


def is_dhcp_offer(packet):
    return packet[0] == 2 and packet[1] == 1


def parse_dhcp_offer(packet):
    # Assuming packet is a byte string
    # The DHCP offer format is:
    # opcode (1 byte), htype (1 byte), hlen (1 byte), hops (1 byte),
    # transaction_id (4 bytes), secs (2 bytes), flags (2 bytes),
    # ciaddr (4 bytes), yiaddr (4 bytes), siaddr (4 bytes), giaddr (4 bytes),
    # chaddr (16 bytes), sname (64 bytes), file (128 bytes), options (variable length)
    transaction_id = int.from_bytes(packet[4:8], byteorder='big')
    yiaddr = '.'.join(str(b) for b in packet[16:20])
    return {'transaction_id': transaction_id, 'yiaddr': yiaddr}


def is_dhcp_ack(packet):
    return packet[0] == 2 and packet[1] == 5


def parse_dhcp_ack(packet):
    # Assuming packet is a byte string
    # The DHCP ack format is similar to the offer format
    transaction_id = int.from_bytes(packet[4:8], byteorder='big')
    yiaddr = '.'.join(str(b) for b in packet[16:20])
    siaddr = '.'.join(str(b) for b in packet[20:24])
    return {'transaction_id': transaction_id, 'yiaddr': yiaddr, 'siaddr': siaddr}


def generate_dhcp_discover():
    message = bytearray()
    message += bytes([1])  # Message type
    message += b"\x01"  # Hardware type: Ethernet (1)
    message += b"\x06"  # Hardware address length: 6 bytes (MAC address)
    message += b"\x00"  # Hops: 0
    message += bytes([random.randint(0, 255)
                     for _ in range(4)])  # Transaction ID
    message += b"\x00\x00"  # Seconds elapsed: 0
    message += b"\x80\x00"  # Flags: 0x8000 (broadcast)
    message += b"\x00\x00\x00\x00"  # Client IP address: 0.0.0.0
    message += b"\x00\x00\x00\x00"  # Your (client) IP address: 0.0.0.0
    message += b"\x00\x00\x00\x00"  # Server IP address: 0.0.0.0
    message += b"\x00\x00\x00\x00"  # Gateway IP address: 0.0.0.0
    # Client hardware address (MAC address)
    message += bytes([random.randint(0, 255) for _ in range(6)])
    message += b"\x00" * 202  # Padding: 202 bytes
    message += b"\x63\x82\x53\x63"  # Magic cookie: DHCP (0x63 0x82 0x53 0x63)
    # Option 53: DHCP Message Type (1 = DHCP Discover)
    message += b"\x35\x01\x01"
    # Option 61: Client identifier (MAC address)
    message += b"\x3d\x06" + bytes([1, 2, 3, 4, 5, 6])
    message += b"\xff"  # End of options
    return message


def generate_dhcp_request(assigned_ip_address, dhcp_server_address, transaction_id):
    message = bytearray()
    message += b'\x01'  # Message type: Boot Request (1)
    message += b'\x01'  # Hardware type: Ethernet
    message += b'\x06'  # Hardware address length: 6
    message += b'\x00'  # Hops: 0
    message += generate_transaction_id()  # Transaction ID
    message += b'\x00\x00'  # Seconds elapsed: 0
    message += b'\x80\x00'  # Bootp flags: 0x8000 (Broadcast) + reserved flags
    message += b'\x00\x00\x00\x00'  # Client IP address: 0.0.0.0
    message += assigned_ip_address.encode()  # Your (client) IP address
    message += b'\x00\x00\x00\x00'  # Next server IP address: 0.0.0.0
    # Relay agent IP address: IP of DHCP server
    message += dhcp_server_address.encode()
    # Client hardware address: 6 bytes of 0x00 (useless for DHCP Request)
    message += b'\x00\x00\x00\x00'
    message += b'\x00' * 202  # Padding: 202 bytes
    message += b'\x63\x82\x53\x63'  # Magic cookie: DHCP (0x63 0x82 0x53 0x63)
    # Option 53: DHCP Message Type (3 = DHCP Request)
    message += b'\x35\x01\x03'
    # Option 50: Requested IP address
    message += b'\x32\x04' + socket.inet_aton(assigned_ip_address)
    # Option 54: DHCP Server Identifier
    message += b'\x36\x04' + socket.inet_aton(dhcp_server_address)
    message += b'\xff'  # End of options
    message[242] = 3
    return message


# Main loop
state = "INIT"
assigned_ip_address = ""
while True:
    if state == "INIT":
        # Send a DHCP discover message
        dhcp_message = generate_dhcp_discover()
        dhcp_socket.sendto(
            dhcp_message, (dhcp_server_address, dhcp_server_port))
        print("Sent DHCP Discover message")
        state = "DISCOVER_SENT"

    elif state == "DISCOVER_SENT":
        # Wait for a DHCP offer message
        dhcp_response, dhcp_server_address = dhcp_socket.recvfrom(1024)
        if is_dhcp_offer(dhcp_response):
            print("Received DHCP Offer message")
            # Parse the DHCP offer message and use the assigned IP address for DNS queries
            assigned_ip_address = parse_dhcp_offer(dhcp_response)
            print(f"Assigned IP address: {assigned_ip_address}")
            # Send a DHCP request message to accept the offered IP address
            transaction_id = generate_transaction_id()
            address = str(assigned_ip_address['yiaddr'])
            print(address)
            dhcp_message = generate_dhcp_request(
                address, dhcp_server_address[0], transaction_id)
            dhcp_socket.sendto(
                dhcp_message, (dhcp_server_address[0], dhcp_server_port))
            print("Sent DHCP Request message")
            state = "REQUEST_SENT"

    elif state == "REQUEST_SENT":
        # Wait for a DHCP acknowledge message
        dhcp_response, dhcp_server_address = dhcp_socket.recvfrom(1024)
        if is_dhcp_ack(dhcp_response):
            print("Received DHCP Acknowledge message")
            # Update the assigned IP address for future DNS queries
            assigned_ip_address = parse_dhcp_ack(dhcp_response)
            print(f"Assigned IP address: {assigned_ip_address}")
            state = "READY"

        else:
            # If the DHCP response is not an acknowledge message, return to the DISCOVER_SENT state
            print("Invalid DHCP response")
            state = "INIT"

    elif state == "READY":
        # Send a DNS query
        dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_query = dns.message.make_query("google.com", "A")
        dns_socket.sendto(dns_query.to_wire(),
                          (dns_server_address, dns_server_port))
        print("Sent DNS query")
        dns_response = dns.message.from_wire(dns_socket.recv(1024))
        print("Received DNS response")
        for answer in dns_response.answer:
            if answer.rdtype == dns.rdatatype.A:
                print(answer.to_text())
        time.sleep(5)  # Wait 5 seconds before sending the next DNS query
