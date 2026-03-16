import threading
import socket
import dns.resolver
import dns.message

# A dictionary that maps domain names to IP addresses
dns_cache = {
    'google.com': '8.8.8.8',
    'yahoo.com': '98.138.219.232'
}


# A function to handle incoming DNS queries
def handle_dns_query(query, client_address, sock):
    # Parse the DNS query message
    try:
        message = dns.message.from_wire(query)
        domain_name = message.question[0].name.to_text().strip('.')

        # Add a dot to the end of the domain name if it does not already have one
        domain_name = dns.name.from_text(domain_name)
        if not domain_name.is_absolute():
            domain_name = domain_name.concatenate(dns.name.root)

        print(
            f'Received DNS query for domain {domain_name.to_text()} from {client_address}')

        # Check if the domain name is in the DNS cache
        if domain_name in dns_cache:
            # Create a DNS response message with the IP address for the domain name
            ip_address = dns_cache[domain_name]
            response = dns.message.make_response(
                message, recursion_available=True)
            response.answer.append(dns.rrset.from_text(
                domain_name, 300, 'IN', 'A', ip_address))

            # Send the response message back to the client
            sock.sendto(response.to_wire(), client_address)

            print(
                f'Sent DNS response for domain {domain_name} to {client_address}')

        else:
            # The domain name is not in the DNS cache, so send a DNS query to the next-level DNS server
            resolver = dns.resolver.Resolver()
            try:
                answer = resolver.resolve(domain_name, 'A')
                response = answer.response.to_wire()
                sock.sendto(response, client_address)

                print(
                    f'Sent DNS query for domain {domain_name} to next-level DNS server and got response')

            except dns.resolver.NXDOMAIN:
                # If the domain name does not exist, return a DNS response with the appropriate error code
                response = dns.message.make_response(
                    message, recursion_available=True, rcode=dns.rcode.NXDOMAIN)
                sock.sendto(response.to_wire(), client_address)

                print(
                    f'Returned DNS response with NXDOMAIN for domain {domain_name} to {client_address}')

    except Exception as e:
        print(f'Error handling DNS query from {client_address}: {e}')

# A function to handle incoming DNS updates


def handle_dns_update(update_message):
    try:
        # Parse the update message and update the DNS cache
        domain_name, ip_address = update_message.split(',')
        dns_cache[domain_name] = ip_address

        print(f'Updated DNS cache with {domain_name}:{ip_address}')

    except Exception as e:
        print(f'Error handling DNS update: {e}')

# A function to listen for incoming DNS queries


def listen_for_dns_queries():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('0.0.0.0', 533))
        print('Started DNS query listener on port 535')
        while True:
            query, client_address = sock.recvfrom(512)
            handle_dns_query(query, client_address, sock)

# A function to listen for incoming DNS updates


def listen_for_dns_updates():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('0.0.0.0', 9898))
        print('Started DNS update listener on port 9898')
        while True:
            update_message, client_address = sock.recvfrom(512)
            handle_dns_update(update_message.decode('utf-8'))

# A function to update the DNS cache when the DHCP server assigns a new IP address to a client


def update_dns_cache(client_id, ip_address):
    try:
        # Update the DNS cache with the new IP address for the client's hostname
        hostname = f'client-{client_id}'
        dns_cache[hostname] = ip_address
        print(f'Updated DNS cache with {hostname}:{ip_address}')
    except Exception as e:
        print(f'Error updating DNS cache: {e}')
# A function to handle incoming DHCP lease update messages


def handle_lease_update(update_message):
    try:
        # Parse the lease update message and update the DNS cache
        client_id, ip_address = update_message.split(',')
        update_dns_cache(client_id, ip_address)
    except Exception as e:
        print(f'Error handling DHCP lease update: {e}')


# Start the DNS query listener thread
dns_query_listener_thread = threading.Thread(target=listen_for_dns_queries)
dns_query_listener_thread.start()

# Start the DNS update listener thread
dns_update_listener_thread = threading.Thread(target=listen_for_dns_updates)
dns_update_listener_thread.start()

# Wait for both threads to complete
dns_query_listener_thread.join()
dns_update_listener_thread.join()
