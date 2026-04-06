"""
Wireless Punch Capture Dashboard
Connects to Pico W over WiFi (TCP) instead of USB serial.

Install: pip install rich
Run:
    1. Connect your laptop to the "PicoPunch" WiFi
    2. python wireless_dashboard.py
"""

import sys
import os
import time
import math
import socket
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

PICO_IP = "192.168.4.1"
PICO_PORT = 8888
SAVE_DIR = r"C:\Users\kvibn\Downloads\punch_data"


class PunchDashboard:
    def __init__(self):
        self.sock = None
        self.buf = ""
        self.punches = []
        self.current_rows = []
        self.capturing = False
        self.current_num = 0
        self.status = "Connecting to Pico..."
        self.last_stats = ""
        self.config_info = ""
        # Create timestamped session folder
        session = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.save_dir = os.path.join(SAVE_DIR, session)
        os.makedirs(self.save_dir, exist_ok=True)

    def connect(self):
        """Connect to Pico TCP server"""
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5)
                self.sock.connect((PICO_IP, PICO_PORT))
                self.sock.settimeout(0.5)
                self.status = "Connected! Waiting for punches..."
                return True
            except (socket.error, OSError) as e:
                self.status = f"Can't reach Pico at {PICO_IP}:{PICO_PORT} - retrying..."
                time.sleep(2)
                return False

    def read_lines(self):
        """Read available lines from TCP socket"""
        lines = []
        try:
            data = self.sock.recv(4096).decode("utf-8", errors="ignore")
            if not data:
                raise ConnectionError("Pico disconnected")
            self.buf += data
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                line = line.strip()
                if line:
                    lines.append(line)
        except socket.timeout:
            pass
        except (ConnectionError, OSError):
            self.status = "Disconnected - reconnecting..."
            self.sock.close()
            self.sock = None
        return lines

    def process_line(self, line):
        if line == "PUNCH_READY":
            self.status = "Armed - waiting for punch"
            return

        if line.startswith("CONFIG:") or line.startswith("INTERVAL:"):
            self.config_info = line
            return

        if line.startswith("PUNCH_START:"):
            self.current_num = int(line.split(":")[1])
            self.current_rows = []
            self.capturing = True
            self.status = f"Receiving punch #{self.current_num}..."
            return

        if line == "PUNCH_END":
            self.capturing = False
            if self.current_rows:
                punch = self.finish_punch()
                self.punches.append(punch)
                self.save_csv(punch)
                self.status = f"Punch #{self.current_num} captured! ({len(self.current_rows)} samples) - Waiting..."
            return

        if line.startswith("STATS:"):
            self.last_stats = line[6:]
            return

        if line == "STOPPED":
            self.status = "Pico stopped"
            return

        if self.capturing:
            parts = line.split(",")
            if len(parts) == 9:
                try:
                    row = {
                        "t": int(parts[0]),
                        "ax": float(parts[1]), "ay": float(parts[2]), "az": float(parts[3]),
                        "gx": float(parts[4]), "gy": float(parts[5]), "gz": float(parts[6]),
                        "fr": int(parts[7]), "fv": float(parts[8])
                    }
                    self.current_rows.append(row)
                except (ValueError, IndexError):
                    pass

    def finish_punch(self):
        peak_a = 0
        peak_g = 0
        peak_f = 0
        for r in self.current_rows:
            a = math.sqrt(r["ax"]**2 + r["ay"]**2 + r["az"]**2)
            g = math.sqrt(r["gx"]**2 + r["gy"]**2 + r["gz"]**2)
            if a > peak_a: peak_a = a
            if g > peak_g: peak_g = g
            if r["fv"] > peak_f: peak_f = r["fv"]
        return {
            "num": self.current_num,
            "rows": list(self.current_rows),
            "peak_a": peak_a,
            "peak_g": peak_g,
            "peak_f": peak_f,
            "samples": len(self.current_rows),
            "time": time.strftime("%H:%M:%S")
        }

    def save_csv(self, punch):
        fname = os.path.join(self.save_dir, f"punch_{punch['num']:03d}.csv")
        with open(fname, "w") as f:
            f.write("t_ms,ax,ay,az,gx,gy,gz,fsr_raw,fsr_v\n")
            for r in punch["rows"]:
                f.write(f"{r['t']},{r['ax']},{r['ay']},{r['az']},{r['gx']},{r['gy']},{r['gz']},{r['fr']},{r['fv']}\n")

    def build_display(self):
        layout = Layout()

        if "Armed" in self.status or "captured" in self.status:
            status_color = "green"
        elif "Receiving" in self.status:
            status_color = "yellow"
        elif "Disconnected" in self.status or "Can't" in self.status:
            status_color = "red"
        else:
            status_color = "cyan"

        tbl = Table(title="Captured Punches", expand=True, border_style="cyan")
        tbl.add_column("#", width=4)
        tbl.add_column("Time", width=10)
        tbl.add_column("Samples", width=8)
        tbl.add_column("Peak Accel", width=12)
        tbl.add_column("Peak Gyro", width=12)
        tbl.add_column("Peak FSR", width=10)
        tbl.add_column("File", width=20)

        for p in self.punches[-10:]:
            a_color = "green" if p["peak_a"] < 4 else "yellow" if p["peak_a"] < 10 else "red"
            tbl.add_row(
                str(p["num"]),
                p["time"],
                str(p["samples"]),
                f"[{a_color}]{p['peak_a']:.2f}g[/{a_color}]",
                f"{p['peak_g']:.0f} d/s",
                f"{p['peak_f']:.2f}V",
                f"punch_{p['num']:03d}.csv"
            )

        if not self.punches:
            tbl.add_row("-", "-", "-", "-", "-", "-", "Hit the sensor!")

        layout.split_column(
            Layout(Panel(
                Text("  Wireless Punch Dashboard  ", style="bold white on blue", justify="center"),
                border_style="blue"
            ), size=3),
            Layout(Panel(
                Text(f"  {self.status}  ", style=f"bold {status_color}", justify="center"),
                border_style=status_color
            ), size=3),
            Layout(Panel(
                Text(f"Total: {len(self.punches)}  |  {self.config_info}  |  {self.last_stats}", justify="center"),
                border_style="dim"
            ), size=3),
            Layout(tbl, ratio=4),
            Layout(Panel(
                Text(f"WiFi: {AP_SSID} @ {PICO_IP}:{PICO_PORT}  |  Ctrl+C to stop  |  CSVs: {os.path.abspath(self.save_dir)}/", style="dim", justify="center"),
                border_style="dim"
            ), size=3),
        )
        return layout

    def run(self):
        console = Console()
        console.print(f"[cyan]Connecting to Pico at {PICO_IP}:{PICO_PORT}...[/cyan]")
        console.print(f"[yellow]Make sure you're connected to the '{AP_SSID}' WiFi![/yellow]")
        console.print(f"[cyan]Saving CSVs to {os.path.abspath(self.save_dir)}/[/cyan]")

        try:
            with Live(self.build_display(), refresh_per_second=10, console=console) as live:
                while True:
                    # Connect if needed
                    if self.sock is None:
                        self.connect()
                        live.update(self.build_display())
                        if self.sock is None:
                            continue

                    # Read and process lines
                    lines = self.read_lines()
                    for line in lines:
                        self.process_line(line)

                    live.update(self.build_display())

        except KeyboardInterrupt:
            console.print(f"\n[yellow]Stopped. {len(self.punches)} punches saved to {os.path.abspath(self.save_dir)}/[/yellow]")
        finally:
            if self.sock:
                self.sock.close()


AP_SSID = "PicoPunch"

def main():
    dash = PunchDashboard()
    dash.run()

if __name__ == "__main__":
    main()
