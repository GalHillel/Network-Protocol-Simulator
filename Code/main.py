"""
Application Launcher

This module provides a GUI application launcher that can start various network services
including HTTP servers, DHCP/DNS servers, and client applications.
"""

import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Optional


class Application(ttk.Frame):
    """
    Main application class that provides a graphical launcher for network services.
    
    Attributes:
        master: The root Tk window.
        style: TTK style configuration.
    """
    
    def __init__(self, master: Optional[tk.Tk] = None) -> None:
        """
        Initialize the Application launcher.
        
        Args:
            master: The parent Tk window.
        """
        super().__init__(master)
        self.master = master
        if self.master:
            self.master.title("Application Launcher")
            self.master.geometry("500x300")
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.pack(fill=tk.BOTH, expand=True)
        self.create_widgets()

    def create_widgets(self) -> None:
        """Create and layout all GUI widgets."""
        # Header
        header_label = ttk.Label(
            self, text="Application Launcher", font=("Helvetica", 24, "bold"))
        header_label.pack(side="top", pady=(10, 20))

        # HTTP Application Button
        http_button = ttk.Button(
            self, text="HTTP Application", command=self.activate_http)
        http_button.pack(pady=(0, 10), ipady=10, ipadx=30, padx=50, fill=tk.X)

        # DHCP and DNS Button
        dhcp_dns_button = ttk.Button(
            self, text="Activate The DHCP and DNS", command=self.activate_dhcp_dns)
        dhcp_dns_button.pack(pady=(0, 10), ipady=10,
                             ipadx=30, padx=50, fill=tk.X)

        # Client Button
        client_button = ttk.Button(
            self, text="Client", command=self.activate_client)
        client_button.pack(pady=(0, 10), ipady=10,
                           ipadx=30, padx=50, fill=tk.X)

    def activate_http(self) -> None:
        """Launch HTTP-related servers and client."""
        subprocess.Popen(["sudo", "python3", "./RUDPserver.py"])
        subprocess.Popen(["sudo", "python3", "./TCPserver.py"])
        subprocess.Popen(["sudo", "python3", "./Client.py"])

    def activate_dhcp_dns(self) -> None:
        """Launch DHCP and DNS servers."""
        subprocess.Popen(["sudo", "python3", "./DNS_Server.py"])
        subprocess.Popen(["sudo", "python3", "./DHCP_Server.py"])

    def activate_client(self) -> None:
        """Launch the client application."""
        subprocess.Popen(["sudo", "python3", "./client1.py"])


root = tk.Tk()
app = Application(master=root)
app.mainloop()
