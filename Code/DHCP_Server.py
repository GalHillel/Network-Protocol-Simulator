"""
DHCP Server Implementation

This module implements a DHCP server that listens for DHCP discovery and request messages,
assigns IP addresses to clients, and manages IP address availability.
"""

import socket
from typing import Optional

dhcp_server_address: str = "0.0.0.0"  # Listen on all available network interfaces
dhcp_server_port: int = 67

dhcp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dhcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
dhcp_socket.bind((dhcp_server_address, dhcp_server_port))
print(f"DHCP server listening on {dhcp_server_address}:{dhcp_server_port}")

ip_range_start: str = "192.168.1.100"
ip_range_end: str = "192.168.1.200"


def is_ip_available(ip_address: str) -> bool:
    """
    Check if an IP address is available by pinging it.
    
    Args:
        ip_address: The IP address to check.
        
    Returns:
        True if the IP address is available, False otherwise.
    """
    icmp_socket = socket.socket(
        socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    icmp_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, 1)
    icmp_socket.settimeout(0.2)
    try:
        icmp_socket.sendto(b"Hello", (ip_address, 1))
        icmp_socket.recvfrom(1024)
        return False  # Another host replied, so IP address is not available
    except socket.timeout:
        return True  # No response, so IP address is available


def generate_dhcp_offer(ip_address: str) -> bytearray:
    """
    Generate a DHCP offer message with the available IP address.
    
    Args:
        ip_address: The IP address to offer to the client.
        
    Returns:
        A bytearray containing the DHCP offer message.
    """
    dhcp_offer = bytearray()
    dhcp_offer += b"\x02"  # Message type: DHCP offer
    dhcp_offer += b"\x01"  # Subnet mask: 255.255.255.0
    dhcp_offer += b"\x03\x06" + \
        bytes(map(int, ip_address.split(".")))  # Offered IP address
    dhcp_offer += b"\x03\x06" + \
        bytes(map(int, dhcp_server_address.split(".")))  # DHCP server IP address
    dhcp_offer += b"\x06\x08" + b"\x08\x08\x08\x08" + \
        b"\x04\x00\x00\x3c"  # DNS server IP address and lease time
    dhcp_offer += b"\xff"  # End of options
    return dhcp_offer


def generate_dhcp_ack(requested_ip_address: str) -> bytearray:
    """
    Generate a DHCP acknowledgement message with the assigned IP address.
    
    Args:
        requested_ip_address: The IP address requested by the client.
        
    Returns:
        A bytearray containing the DHCP acknowledgement message.
    """
    dhcp_ack = bytearray()
    dhcp_ack += b"\x05"  # Message type: DHCP acknowledgement
    dhcp_ack += requested_ip_address.encode()  # Assigned IP address
    dhcp_ack += b"\x00\x00\x00\x00"  # Subnet mask
    dhcp_ack += b"\x00\x00\x00\x00"  # Default gateway
    dhcp_ack += b"\x00\x00\x00\x00"  # DNS server IP address
    dhcp_ack += b"\x00" * (236 - len(dhcp_ack))
    dhcp_ack[0] = 2
    dhcp_ack[1] = 5
    return dhcp_ack


while True:
    dhcp_request, client_address = dhcp_socket.recvfrom(1024)
    print(f"Received DHCP request from {client_address}:")

    if len(dhcp_request) < 236:
        print("messages that are shorter than the DHCP header (236 bytes)")
        continue

    # Parse the DHCP request message
    dhcp_message_type = dhcp_request[242]
    dhcp_client_hw_addr = dhcp_request[28:34]
    dhcp_requested_ip = dhcp_request[12:16]

    if dhcp_message_type == 1:  # DHCP discover message
        # Find an available IP address
        ip_address: Optional[str] = None
        for i in range(int(ip_range_start.split(".")[-1]), int(ip_range_end.split(".")[-1])):
            test_ip_address = "192.168.1." + str(i)
            if is_ip_available(test_ip_address):
                ip_address = test_ip_address
                break

        if ip_address is None:
            # No available IP addresses, so can't generate DHCP offer message
            print("No available IP addresses.")
            continue

        # Generate a DHCP offer message with the available IP address
        dhcp_offer = generate_dhcp_offer(ip_address)
        # Send the DHCP offer message to the client
        dhcp_socket.sendto(dhcp_offer, client_address)
        print(
            f"Sent DHCP offer to {client_address} with IP address {ip_address}")

    elif dhcp_message_type == 3:  # DHCP request message
        # Check if the requested IP address is available
        requested_ip_address = socket.inet_ntoa(dhcp_requested_ip)
        if not is_ip_available(requested_ip_address):
            # Generate a DHCP negative acknowledgement message
            dhcp_nak = bytearray()
            dhcp_nak += b"\x06"  # Message type: DHCP negative acknowledgement
            # Add other DHCP message fields (e.g., error message)
            dhcp_nak += b"\x00" * (236 - len(dhcp_nak))
            dhcp_socket.sendto(dhcp_nak, client_address)
            print(f"Sent DHCP negative acknowledgement to {client_address}")
            continue

        # Generate a DHCP acknowledgement message with the assigned IP address
        dhcp_ack = generate_dhcp_ack(requested_ip_address)
        dhcp_socket.sendto(dhcp_ack, client_address)
        print(
            f"Sent DHCP acknowledgement to {client_address} with IP address {requested_ip_address}")

        print(
            f"Assigned IP address {requested_ip_address} to {client_address}")
    else:
        print("Unsupported DHCP message type")
        continue
