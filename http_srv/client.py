"""
Unified Protocol Client UI

Professional Tkinter GUI for testing HTTP file transfers over both
TCP and RUDP transport protocols. Demonstrates the difference between
reliable TCP streams and custom RUDP reliability layers.
"""

import socket
import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

class _RUDPClientPlaceholder:
    def __init__(self, *args, **kwargs) -> None: pass
    def __enter__(self) -> "_RUDPClientPlaceholder": return self
    def __exit__(self, *args) -> None: pass
    def send_request(self, *args) -> str: return "Error: RUDP client not available."

try:
    from rudp.rudp_client import RUDPClient  # type: ignore
except ImportError:
    RUDPClient = _RUDPClientPlaceholder


class UnifiedClient(tk.Tk):
    """Protocol Client Dashboard with TCP and RUDP transport options.

    Provides a GUI for sending file download requests to either
    the TCP HTTP server or the RUDP server, displaying results.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Protocol Client Dashboard")
        self.geometry("520x420")
        self.resizable(False, False)

        # Initialize attributes with correct types to satisfy strict analyzer
        self.url_entry: ttk.Entry = ttk.Entry(self)
        self.file_entry: ttk.Entry = ttk.Entry(self)
        self.download_btn: ttk.Button = ttk.Button(self)
        self.status_label: ttk.Label = ttk.Label(self)

        # Initialize variables before widgets
        self.protocol_var = tk.StringVar(value="TCP")
        self.status_var = tk.StringVar(value="Ready")

        # Create widgets (which will overwrite self.url_entry etc.)
        self._create_widgets()

    def _create_widgets(self) -> None:
        """Build the GUI layout."""
        style = ttk.Style(self)
        style.configure("TLabel", font=("Segoe UI", 10))

        container = ttk.Frame(self, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            container,
            text="Request Settings",
            font=("Segoe UI", 12, "bold"),
        )
        header.pack(anchor=tk.W, pady=10)

        # URL Input
        l1 = ttk.Label(container, text="Target URL:")
        l1.pack(anchor=tk.W)
        url_entry = self.url_entry
        url_entry.configure(width=55)
        url_entry.insert(tk.END, "https://www.africau.edu/images/default/sample.pdf")
        url_entry.pack(fill=tk.X, pady=5)

        # Filename Input
        l2 = ttk.Label(container, text="Local Filename:")
        l2.pack(anchor=tk.W)
        file_entry = self.file_entry
        file_entry.configure(width=55)
        file_entry.insert(tk.END, "downloaded_file")
        file_entry.pack(fill=tk.X, pady=5)

        # Protocol Choice
        l3 = ttk.Label(container, text="Transport Protocol:")
        l3.pack(anchor=tk.W, pady=(10, 0))
        radio_frame = ttk.Frame(container)
        radio_frame.pack(fill=tk.X, pady=5)

        p_var = self.protocol_var
        r1 = ttk.Radiobutton(
            radio_frame,
            text="HTTP over TCP (Reliable Stream)",
            variable=p_var,
            value="TCP",
        )
        r1.pack(side=tk.LEFT, padx=10)
        
        r2 = ttk.Radiobutton(
            radio_frame,
            text="HTTP over RUDP (Custom ARQ)",
            variable=p_var,
            value="RUDP",
        )
        r2.pack(side=tk.LEFT, padx=10)

        # Action Button
        btn = self.download_btn
        btn.configure(text="Execute Download", command=self._handle_download)
        btn.pack(pady=20, ipady=5)

        # Status
        s_var = self.status_var
        lbl = self.status_label
        lbl.configure(
            textvariable=s_var,
            font=("Segoe UI", 9, "italic"),
            foreground="blue",
        )
        lbl.pack(pady=5)

    def _handle_download(self) -> None:
        """Dispatch download in a background thread to keep the UI responsive."""
        url = self.url_entry.get().strip()
        filename = self.file_entry.get().strip()
        protocol = self.protocol_var.get()

        if not url or not filename:
            messagebox.showwarning("Input Error", "Provide both a URL and filename.")
            return

        self.status_var.set(f"Connecting via {protocol}...")
        self.download_btn.configure(state="disabled")
        self.update_idletasks()

        threading.Thread(
            target=self._run_download,
            args=(url, filename, protocol),
            daemon=True,
        ).start()

    def _run_download(self, url: str, filename: str, protocol: str) -> None:
        """Execute the download off the main thread."""
        try:
            if protocol == "TCP":
                response = self._tcp_request(url, filename)
            else:
                response = self._rudp_request(url, filename)

            self.after(0, self._show_result, response)
        except Exception as exc:
            self.after(0, self._show_error, str(exc))

    def _show_result(self, response: str) -> None:
        self.status_var.set("Response received")
        self.download_btn.configure(state="normal")
        messagebox.showinfo("Server Response", response)

    def _show_error(self, msg: str) -> None:
        self.status_var.set("Error")
        self.download_btn.configure(state="normal")
        messagebox.showerror("Transfer Error", msg)

    @staticmethod
    def _tcp_request(url: str, filename: str) -> str:
        """Send request via TCP."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(30)
            sock.connect(("localhost", 9898))
            sock.sendall(f"{url},{filename}".encode("utf-8"))
            return sock.recv(4096).decode("utf-8")

    @staticmethod
    def _rudp_request(url: str, filename: str) -> str:
        """Send request via RUDP."""
        with RUDPClient("localhost", 7878) as client:
            return client.send_request(url, filename)


def main() -> None:
    """Launch the Protocol Client Dashboard."""
    app = UnifiedClient()
    app.mainloop()


if __name__ == "__main__":
    main()
