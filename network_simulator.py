"""
Network Protocol Simulator — Main Entry Point

Professional GUI dashboard for launching and managing protocol servers
and clients. Acts as a service orchestrator, spawning protocol servers
as independent subprocesses.

Features:
    - Launch HTTP/TCP and RUDP servers
    - Launch DNS and DHCP infrastructure services
    - Open the Protocol Client Dashboard
    - Graceful subprocess cleanup on exit
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List


class SimulationManager(tk.Tk):
    """Main GUI for the Network Protocol Simulator.

    Provides buttons to launch each protocol component as a separate
    process, with automatic cleanup on window close.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Network Protocol Simulator")
        self.geometry("620x480")
        self.configure(bg="#f5f5f5")
        self.resizable(False, False)

        self._style = ttk.Style(self)
        self._style.theme_use("clam")
        self._style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background="#f5f5f5")
        self._style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), background="#f5f5f5")
        self._style.configure("Action.TButton", font=("Segoe UI", 11), padding=10)

        self._processes: List[subprocess.Popen] = []
        self._project_root = os.path.dirname(os.path.abspath(__file__))
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self) -> None:
        """Build the dashboard layout."""
        main = ttk.Frame(self, padding=24)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main, text="🌐 Network Protocol Stack Simulator", style="Header.TLabel").pack(pady=(0, 20))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.BOTH, expand=True)

        # ── HTTP & File Transfer ──
        ttk.Label(btn_frame, text="⬡ HTTP & File Transfer", style="Section.TLabel").pack(anchor=tk.W, pady=(10, 5))
        ttk.Button(
            btn_frame,
            text="Launch HTTP Stack (TCP + RUDP Servers)",
            style="Action.TButton",
            command=self._launch_http_stack,
        ).pack(fill=tk.X, pady=5)

        # ── Infrastructure ──
        ttk.Label(btn_frame, text="⬡ Network Infrastructure", style="Section.TLabel").pack(anchor=tk.W, pady=(15, 5))
        ttk.Button(
            btn_frame,
            text="Start DNS & DHCP Core Services",
            style="Action.TButton",
            command=self._launch_infra,
        ).pack(fill=tk.X, pady=5)

        # ── Clients ──
        ttk.Label(btn_frame, text="⬡ Clients", style="Section.TLabel").pack(anchor=tk.W, pady=(15, 5))
        ttk.Button(
            btn_frame,
            text="Open Protocol Client Dashboard",
            style="Action.TButton",
            command=self._launch_client,
        ).pack(fill=tk.X, pady=5)

        # Footer
        ttk.Label(
            main,
            text="Note: Some services may require elevated privileges.",
            foreground="gray",
            font=("Segoe UI", 9, "italic"),
        ).pack(side=tk.BOTTOM, pady=10)

    def _run_script(self, relative_path: str) -> None:
        """Launch a Python script as a subprocess."""
        path = os.path.join(self._project_root, relative_path)
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Script not found: {path}")
            return

        try:
            proc = subprocess.Popen(
                [sys.executable, path],
                cwd=self._project_root,
            )
            self._processes.append(proc)
        except Exception as exc:
            messagebox.showerror("Launch Error", str(exc))

    def _launch_http_stack(self) -> None:
        self._run_script(os.path.join("http_srv", "tcp_server.py"))
        self._run_script(os.path.join("rudp", "rudp_server.py"))
        messagebox.showinfo("HTTP Stack", "TCP and RUDP servers launched.")

    def _launch_infra(self) -> None:
        self._run_script(os.path.join("dns_srv", "dns_server.py"))
        self._run_script(os.path.join("dhcp", "dhcp_server.py"))
        messagebox.showinfo("Infrastructure", "DNS and DHCP services launched.")

    def _launch_client(self) -> None:
        self._run_script(os.path.join("http_srv", "client.py"))

    def _on_closing(self) -> None:
        """Terminate all child processes and close the window."""
        for proc in self._processes:
            try:
                proc.terminate()
            except OSError:
                pass
        self.destroy()


def main() -> None:
    """Launch the Network Protocol Simulator dashboard."""
    app = SimulationManager()
    app.mainloop()


if __name__ == "__main__":
    main()
