#!/usr/bin/env python3
"""
Standalone test: discover boards and print live CoP data from each one.
Press S to record 30 seconds of data, then view a plot.
Press Ctrl+C to stop.
"""

import socket
import struct
import time
import sys
import threading
import msvcrt
import csv
import os
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

from local_ip_fetch import Ip

RECORD_SECS = 20
RECORDINGS_DIR = "./recordings"
G = 1   # N -> kg


def discover_boards():
    """Discover MOBBO boards — broadcast first, then direct subnet scan."""
    local_ip     = Ip()
    broadcast_ip = local_ip.Local_ip()[0]
    UDP_PORT     = 23000
    MESSAGE      = "Hey!mobbos"
    unique       = set()

    print(f"Phase 1: Broadcast on {broadcast_ip}:{UDP_PORT} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(2)
    deadline = time.time() + 4
    while time.time() < deadline:
        try:
            sock.sendto(MESSAGE.encode(), (broadcast_ip, UDP_PORT))
        except OSError:
            pass
        try:
            _, addr = sock.recvfrom(1024)
            if addr not in unique:
                unique.add(addr)
                print(f"  Found (broadcast): {addr[0]}")
        except (socket.timeout, ConnectionResetError):
            continue
    sock.close()

    if not unique:
        prefix = broadcast_ip.rsplit('.', 1)[0]
        print(f"Phase 2: Direct scan {prefix}.1-254 ...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.15)
        for h in range(1, 255):
            try:
                sock.sendto(MESSAGE.encode(), (f"{prefix}.{h}", UDP_PORT))
            except OSError:
                pass
        time.sleep(0.3)
        deadline = time.time() + 3
        while time.time() < deadline:
            try:
                _, addr = sock.recvfrom(1024)
                if addr not in unique:
                    unique.add(addr)
                    print(f"  Found (direct): {addr[0]}")
            except socket.timeout:
                for h in range(1, 255):
                    try:
                        sock.sendto(MESSAGE.encode(), (f"{prefix}.{h}", UDP_PORT))
                    except OSError:
                        pass
            except ConnectionResetError:
                continue
        sock.close()

    ips = [a[0] for a in unique]
    print(f"\nDiscovered {len(ips)} boards: {ips}\n")
    return ips


def plot_recording(recorded, session_dir):
    """7 separate subplots per board: F1 F2 F3 F4 COPx COPy Weight(kg).
    Saves a PNG alongside the CSV in session_dir."""
    SUBPLOTS = [
        ("f1",   "F1 (N)",       "#e74c3c"),
        ("f2",   "F2 (N)",       "#3498db"),
        ("f3",   "F3 (N)",       "#2ecc71"),
        ("f4",   "F4 (N)",       "#f39c12"),
        ("copx", "COPx (cm)",    "#1abc9c"),
        ("copy", "COPy (cm)",    "#e67e22"),
        ("w_kg", "Weight (kg)",  "#9b59b6"),
    ]
    N_SUB = len(SUBPLOTS)

    for ip in sorted(recorded.keys()):
        d = recorded[ip]
        t = np.array(d["t"])
        t -= t[0]

        fig = plt.figure(figsize=(14, 2.4 * N_SUB))
        fig.suptitle(f"Board {ip} — {RECORD_SECS} s recording", fontsize=12)
        gs  = gridspec.GridSpec(N_SUB, 1, hspace=0.15, figure=fig)

        axes = []
        for i, (key, ylabel, color) in enumerate(SUBPLOTS):
            ax = fig.add_subplot(gs[i], sharex=axes[0] if axes else None)
            y  = np.array(d[key])
            ax.plot(t, y, color=color, lw=0.9)
            ax.set_ylabel(ylabel, fontsize=8)
            ax.grid(True, alpha=0.25)
            ax.tick_params(labelsize=7)
            if i < N_SUB - 1:
                plt.setp(ax.get_xticklabels(), visible=False)
            axes.append(ax)

        axes[-1].set_xlabel("Time (s)", fontsize=9)
        plt.tight_layout()

        # Save PNG next to the CSV
        safe_ip  = ip.replace(".", "_")
        png_path = os.path.join(session_dir, f"board_{safe_ip}.png")
        fig.savefig(png_path, dpi=150)
        print(f"  Plot saved: {png_path}")

    plt.show()


def stream_cop_data(board_ips):
    """Send wake messages, print live CoP data, handle S-key recording."""
    UDP_PORT = 23000
    MESSAGE  = "Hey!mobbos"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.05)          # tiny timeout — never blocks the print loop

    for ip in board_ips:
        try:
            sock.sendto(MESSAGE.encode(), (ip, UDP_PORT))
        except OSError:
            pass

    counters = {}
    rows     = {}                  # ip -> latest formatted string

    HEADER = (f"{'Board IP':<20} {'COPx':>8} {'COPy':>8} "
              f"{'F1':>8} {'F2':>8} {'F3':>8} {'F4':>8} {'Weight':>8}")
    SEP    = "-" * 88

    print(HEADER)
    print(SEP)
    for ip in board_ips:
        rows[ip] = ""
        print()                    # reserve one line per board
    print("  Press S to record 30 s — Ctrl+C to quit")
    sys.stdout.flush()

    n_boards = len(board_ips)

    def redraw():
        # Move cursor up to the first board line and overwrite each with \r
        sys.stdout.write(f"\033[{n_boards + 1}A")   # +1 for the hint line
        for ip in sorted(rows):
            sys.stdout.write(f"\r{rows[ip]}\033[K\n")
        sys.stdout.write(f"\r  Press S to record 30 s — Ctrl+C to quit\033[K\n")
        sys.stdout.flush()

    # ---------- recording state (shared with key-listener thread) ----------
    _recording    = threading.Event()
    _pending_plot = {"data": None, "session_dir": None}

    def _key_listener():
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch().lower()
                if ch == b's' and not _recording.is_set():
                    _recording.set()
            time.sleep(0.05)

    threading.Thread(target=_key_listener, daemon=True).start()

    # ---------- main receive loop ----------
    try:
        missed       = 0
        rec_start    = None
        rec_data     = {}
        session_dir  = None

        while True:
            # --- start of a new recording window ---
            if _recording.is_set() and rec_start is None:
                rec_start   = time.time()
                stamp       = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_dir = os.path.join(RECORDINGS_DIR, f"force_recording_{stamp}")
                os.makedirs(session_dir, exist_ok=True)
                rec_data  = {ip: {"t": [], "f1": [], "f2": [], "f3": [], "f4": [],
                                  "w": [], "w_kg": [], "copx": [], "copy": []}
                             for ip in board_ips}
                # Print status below live rows without disturbing them
                sys.stdout.write(f"\r\033[K  Recording... 0 / {RECORD_SECS} s\n")
                sys.stdout.flush()

            try:
                data, addr = sock.recvfrom(2048)

                # XOR checksum
                if len(data) >= 5:
                    chk = 0
                    for b in data[4:]:
                        chk ^= b
                    if chk != data[3]:
                        continue

                if len(data) == 34:
                    unpacked = struct.unpack('4c7fh', data)
                    f1, f2, f3, f4, copx, copy, w, _ = unpacked[4:]
                elif len(data) == 32:
                    unpacked = struct.unpack('4c7f', data)
                    _, f1, f2, f3, f4, copx, copy = unpacked[4:]
                    w = f1 + f2 + f3 + f4
                else:
                    continue

                ip = addr[0]
                counters[ip] = counters.get(ip, 0) + 1

                if ip not in rows:
                    rows[ip] = ""

                rows[ip] = (f"{ip:<20} {copx:>+8.2f} {copy:>+8.2f} "
                            f"{f1:>8.2f} {f2:>8.2f} {f3:>8.2f} {f4:>8.2f} {w:>8.2f}")
                redraw()
                missed = 0

                # --- accumulate recording ---
                if _recording.is_set() and rec_start is not None and ip in rec_data:
                    now     = time.time()
                    elapsed = now - rec_start
                    rec_data[ip]["t"].append(now)
                    rec_data[ip]["f1"].append(f1)
                    rec_data[ip]["f2"].append(f2)
                    rec_data[ip]["f3"].append(f3)
                    rec_data[ip]["f4"].append(f4)
                    rec_data[ip]["w"].append(w)
                    rec_data[ip]["w_kg"].append(w / G)
                    rec_data[ip]["copx"].append(copx)
                    rec_data[ip]["copy"].append(copy)

                    sys.stdout.write(
                        f"\r\033[K  Recording... {elapsed:.1f} / {RECORD_SECS} s")
                    sys.stdout.flush()

                    if elapsed >= RECORD_SECS:
                        sys.stdout.write(f"\r\033[K  Recording done — saving CSV...\n")
                        sys.stdout.flush()

                        # Save one CSV per board (same format as record_force.py)
                        for bip, d in rec_data.items():
                            safe = bip.replace(".", "_")
                            path = os.path.join(session_dir, f"board_{safe}.csv")
                            with open(path, "w", newline="") as fh:
                                w_ = csv.writer(fh)
                                w_.writerow(["time_s", "f1_N", "f2_N", "f3_N", "f4_N",
                                             "W_N", "W_kg", "copx_cm", "copy_cm"])
                                t0 = d["t"][0]
                                for i in range(len(d["t"])):
                                    w_.writerow([
                                        f"{d['t'][i]-t0:.6f}",
                                        f"{d['f1'][i]:.4f}", f"{d['f2'][i]:.4f}",
                                        f"{d['f3'][i]:.4f}", f"{d['f4'][i]:.4f}",
                                        f"{d['w'][i]:.4f}",  f"{d['w_kg'][i]:.5f}",
                                        f"{d['copx'][i]:.4f}", f"{d['copy'][i]:.4f}",
                                    ])
                            print(f"  CSV saved: {path}")

                        _pending_plot["data"]        = {k: v for k, v in rec_data.items()}
                        _pending_plot["session_dir"] = session_dir
                        _recording.clear()
                        rec_start   = None
                        rec_data    = {}
                        session_dir = None

            except socket.timeout:
                missed += 1
                if missed % 20 == 0:   # re-send wake every ~1 s (20 × 0.05 s)
                    for ip in board_ips:
                        try:
                            sock.sendto(MESSAGE.encode(), (ip, UDP_PORT))
                        except OSError:
                            pass

            except ConnectionResetError:
                continue

            # --- show plot when ready (blocks until window is closed) ---
            if _pending_plot["data"] is not None:
                plot_recording(_pending_plot["data"], _pending_plot["session_dir"])
                _pending_plot["data"]        = None
                _pending_plot["session_dir"] = None
                # Redraw terminal header after returning from plot window
                print(HEADER)
                print(SEP)
                for ip in sorted(rows):
                    print(rows[ip])
                print("\n  Press S to record again — Ctrl+C to quit")
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        sock.close()
        print(f"\nTotal packets received per board:")
        for ip, cnt in sorted(counters.items()):
            print(f"  {ip}: {cnt} packets")


if __name__ == "__main__":
    boards = discover_boards()
    if not boards:
        print("No boards found. Exiting.")
        sys.exit(1)
    stream_cop_data(boards)
