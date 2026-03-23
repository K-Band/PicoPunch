"""
Punch Capture Dashboard - runs on your laptop.
Reads punch data from Pico over USB serial, displays live dashboard,
saves each punch as a CSV file.

Install: pip install pyserial rich
Run:     python punch_dashboard.py
         python punch_dashboard.py COM5
"""

import sys
import os
import time
import math
import serial
import serial.tools.list_ports
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

BAUD = 115200
SAVE_DIR = "punch_data"


def find_pico():
    for p in serial.tools.list_ports.comports():
        vid = p.vid or 0
        desc = (p.description or "").lower()
        if vid == 0x2E8A or "pico" in desc or "board in fs mode" in desc:
            return p.device
    ports = serial.tools.list_ports.comports()
    if ports:
        return ports[0].device
    return None


class PunchDashboard:
    def __init__(self, port):
        self.ser = serial.Serial(port, BAUD, timeout=0.5)
        self.punches = []
        self.current_rows = []
        self.capturing = False
        self.current_num = 0
        self.status = "Waiting for Pico..."
        self.last_fsr = 0.0
        self.last_accel = 0.0
        self.last_stats = ""
        self.config_info = ""
        os.makedirs(SAVE_DIR, exist_ok=True)

    def process_line(self, line):
        line = line.strip()
        if not line:
            return

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
            self.status = f"Capturing punch #{self.current_num}..."
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
                    self.last_fsr = row["fv"]
                    self.last_accel = math.sqrt(row["ax"]**2 + row["ay"]**2 + row["az"]**2)
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
        fname = os.path.join(SAVE_DIR, f"punch_{punch['num']:03d}.csv")
        with open(fname, "w") as f:
            f.write("t_ms,ax,ay,az,gx,gy,gz,fsr_raw,fsr_v\n")
            for r in punch["rows"]:
                f.write(f"{r['t']},{r['ax']},{r['ay']},{r['az']},{r['gx']},{r['gy']},{r['gz']},{r['fr']},{r['fv']}\n")

    def build_display(self):
        layout = Layout()

        status_color = "green" if "Armed" in self.status or "captured" in self.status else "yellow" if "Capturing" in self.status else "cyan"

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
                Text("  Punch Capture Dashboard  ", style="bold white on blue", justify="center"),
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
                Text(f"Ctrl+C to stop  |  CSVs saved to {os.path.abspath(SAVE_DIR)}/", style="dim", justify="center"),
                border_style="dim"
            ), size=3),
        )
        return layout

    def run(self):
        console = Console()
        console.print(f"[cyan]Connected to {self.ser.port}[/cyan]")
        console.print(f"[cyan]Saving CSVs to {os.path.abspath(SAVE_DIR)}/[/cyan]")
        console.print("[yellow]Waiting for Pico... (unplug/replug if needed)[/yellow]")

        try:
            with Live(self.build_display(), refresh_per_second=10, console=console) as live:
                while True:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.process_line(line)
                        live.update(self.build_display())
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Stopped. {len(self.punches)} punches saved to {os.path.abspath(SAVE_DIR)}/[/yellow]")
        finally:
            self.ser.close()


def main():
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_pico()
        if not port:
            print("No Pico found! Plug it in or specify COM port.")
            return

    dash = PunchDashboard(port)
    dash.run()


if __name__ == "__main__":
    main()
