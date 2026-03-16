"""
HTTP Downloader Client

This module provides a GUI client for downloading files using either TCP or RUDP protocols.
The client connects to a server, sends a URL and filename, and receives the downloaded content.
"""

import socket
import tkinter as tk
from typing import Optional

# Global client socket
client_socket: Optional[socket.socket] = None


def connect() -> None:
    """
    Initiates connection to the server and downloads the requested file.
    
    Reads URL, protocol, and filename from GUI inputs, creates appropriate socket,
    and sends download request to server.
    """
    global client_socket
    url = url_input.get().strip()
    protocol = protocol_var.get()
    filename = filename_input.get().strip()

    # check if URL and filename are not empty
    if not url or not filename:
        response_label.config(text='Please provide a valid URL and filename')
        return

    host = socket.gethostname()

    tcp_port = 9898
    rudp_port = 7878

    if protocol.upper() == 'TCP':
        sock_type = socket.SOCK_STREAM
        port = tcp_port
    elif protocol.upper() == 'RUDP':
        sock_type = socket.SOCK_DGRAM
        port = rudp_port
    else:
        response_label.config(text='Invalid protocol choice')
        return

    try:
        client_socket = socket.socket(socket.AF_INET, sock_type)

        client_socket.connect((host, port))

        message = f"{url},{filename}"
        client_socket.sendto(message.encode('utf-8'), (host, port))

        response, server_address = client_socket.recvfrom(1024)

        response_label.config(text=response.decode('utf-8'))

    except Exception as e:
        response_label.config(text=f"Error: {e}")
    finally:
        # close the socket
        if client_socket:
            client_socket.close()


# create GUI
root = tk.Tk()
root.title('HTTP Downloader')
root.geometry('400x300')

url_label = tk.Label(root, text='URL:')
url_label.pack(pady=10)

url_input = tk.Entry(root, width=30)
url_input.pack()

protocol_label = tk.Label(root, text='Protocol:')
protocol_label.pack(pady=10)

protocol_var = tk.StringVar()
tcp_rb = tk.Radiobutton(root, text='TCP', variable=protocol_var, value='TCP')
rudp_rb = tk.Radiobutton(
    root, text='RUDP', variable=protocol_var, value='RUDP')
tcp_rb.pack()
rudp_rb.pack()

filename_label = tk.Label(root, text='Filename:')
filename_label.pack(pady=10)

filename_input = tk.Entry(root, width=30)
filename_input.pack()

connect_button = tk.Button(root, text='Download', command=connect)
connect_button.pack(pady=20)

response_label = tk.Label(root, text='')
response_label.pack()

root.mainloop()
