#!/usr/bin/env python3
"""
MOBBO MOCAP Sync recorder.
Discovers MOBBO boards, displays live force / CoP / MOCAP_SYNC data.

  Press X  — start recording
  Press S  — stop recording and save CSV
  Ctrl+C   — quit (saves any in-progress recording)

CSV columns: time_s, f1_N, f2_N, f3_N, f4_N, W_N, W_kg, copx_cm, copy_cm, mocap_sync
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

from local_ip_fetch import Ip

RECORDINGS_DIR  = "./recordings"
G               = 9.81
MOCAP_SYNC_BIT  = 0x10   # bit in status1 byte set by firmware


# ──────────────────────────────────────────────────────────────────────────────
# Board discovery (identical to test_cop_data.py)
# ──────────────────────────────────────────────────────────────────────────────
def discover_boards():
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


# ──────────────────────────────────────────────────────────────────────────────
# CSV save helper
# ──────────────────────────────────────────────────────────────────────────────
def _save_csv(rec_data, session_dir):
    for bip, d in rec_data.items():
        if not d["t"]:
            print(f"  No data for {bip} — skipping.")
            continue
        safe = bip.replace(".", "_")
        path = os.path.join(session_dir, f"board_{safe}.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["time_s", "f1_N", "f2_N", "f3_N", "f4_N",
                             "W_N", "W_kg", "copx_cm", "copy_cm", "mocap_sync"])
            t0 = d["t"][0]
            for i in range(len(d["t"])):
                writer.writerow([
                    f"{d['t'][i] - t0:.6f}",
                    f"{d['f1'][i]:.4f}",    f"{d['f2'][i]:.4f}",
                    f"{d['f3'][i]:.4f}",    f"{d['f4'][i]:.4f}",
                    f"{d['w'][i]:.4f}",     f"{d['w_kg'][i]:.5f}",
                    f"{d['copx'][i]:.4f}",  f"{d['copy'][i]:.4f}",
                    d["mocap_sync"][i],
                ])
        print(f"  CSV saved: {path}")


# ──────────────────────────────────────────────────────────────────────────────
# Main stream + record loop
# ──────────────────────────────────────────────────────────────────────────────
def stream_and_record(board_ips):
    UDP_PORT = 23000
    MESSAGE  = "Hey!mobbos"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.05)

    for ip in board_ips:
        try:
            sock.sendto(MESSAGE.encode(), (ip, UDP_PORT))
        except OSError:
            pass

    counters = {}
    rows     = {}

    HEADER = (f"{'Board IP':<20} {'SYNC':>5} {'COPx':>8} {'COPy':>8} "
              f"{'F1':>8} {'F2':>8} {'F3':>8} {'F4':>8} {'Weight':>8}")
    SEP    = "-" * 96

    print(HEADER)
    print(SEP)
    for ip in board_ips:
        rows[ip] = ""
        print()
    hint = "Press X to start recording — S to stop and save — Ctrl+C to quit"
    print(f"  {hint}")
    sys.stdout.flush()

    n_boards = len(board_ips)

    def redraw():
        sys.stdout.write(f"\033[{n_boards + 1}A")
        for ip in sorted(rows):
            sys.stdout.write(f"\r{rows[ip]}\033[K\n")
        sys.stdout.write(f"\r  {hint}\033[K\n")
        sys.stdout.flush()

    # Recording state shared with key-listener thread
    _do_start = threading.Event()
    _do_stop  = threading.Event()

    def _key_listener():
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch().lower()
                if ch == b'x':
                    _do_start.set()
                elif ch == b's':
                    _do_stop.set()
            time.sleep(0.05)

    threading.Thread(target=_key_listener, daemon=True).start()

    try:
        missed      = 0
        recording   = False
        rec_start   = None
        rec_data    = {}
        session_dir = None

        while True:
            # ── Start recording ──────────────────────────────────────────────
            if _do_start.is_set() and not recording:
                _do_start.clear()
                recording   = True
                rec_start   = time.time()
                stamp       = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_dir = os.path.join(RECORDINGS_DIR, f"mocap_recording_{stamp}")
                os.makedirs(session_dir, exist_ok=True)
                rec_data = {ip: {"t": [], "f1": [], "f2": [], "f3": [], "f4": [],
                                 "w": [], "w_kg": [], "copx": [], "copy": [],
                                 "mocap_sync": []}
                            for ip in board_ips}
                hint = "Recording...  (press S to stop and save)"

            # ── Stop recording ───────────────────────────────────────────────
            if _do_stop.is_set() and recording:
                _do_stop.clear()
                recording = False
                sys.stdout.write("\r\033[K  Saving CSV...\n")
                sys.stdout.flush()
                _save_csv(rec_data, session_dir)
                rec_start   = None
                rec_data    = {}
                session_dir = None
                hint = "Saved!  Press X to record again — S to stop — Ctrl+C to quit"

            # ── Receive packet ───────────────────────────────────────────────
            try:
                data, addr = sock.recvfrom(2048)

                # XOR checksum on payload bytes (bytes 4 onward) vs byte 3
                if len(data) >= 5:
                    chk = 0
                    for b in data[4:]:
                        chk ^= b
                    if chk != data[3]:
                        continue

                # Parse header (always 4 bytes)
                hdr = struct.unpack('<4B', data[:4])
                status1    = hdr[1]
                mocap_sync = 1 if (status1 & MOCAP_SYNC_BIT) else 0

                if len(data) == 32:
                    # Game packet: header(4) + [t, f1, f2, f3, f4, copx, copy](7 floats)
                    fl = struct.unpack('<7f', data[4:])
                    _t, f1, f2, f3, f4, copx, copy = fl
                    w = f1 + f2 + f3 + f4
                elif len(data) == 34:
                    # Validation packet: header(4) + [f1,f2,f3,f4,copx,copy,W](7 floats) + int16
                    fl = struct.unpack('<7f', data[4:32])
                    f1, f2, f3, f4, copx, copy, w = fl
                else:
                    continue

                ip = addr[0]
                counters[ip] = counters.get(ip, 0) + 1
                if ip not in rows:
                    rows[ip] = ""

                sync_label = " HI" if mocap_sync else " LO"
                rows[ip] = (f"{ip:<20} {sync_label:>5} {copx:>+8.2f} {copy:>+8.2f} "
                            f"{f1:>8.2f} {f2:>8.2f} {f3:>8.2f} {f4:>8.2f} {w:>8.2f}")
                redraw()
                missed = 0

                # ── Accumulate ───────────────────────────────────────────────
                if recording and rec_start is not None and ip in rec_data:
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
                    rec_data[ip]["mocap_sync"].append(mocap_sync)
                    hint = f"Recording...  {elapsed:.1f} s  (press S to stop and save)"

            except socket.timeout:
                missed += 1
                if missed % 20 == 0:          # re-ping every ~1 s
                    for ip in board_ips:
                        try:
                            sock.sendto(MESSAGE.encode(), (ip, UDP_PORT))
                        except OSError:
                            pass
            except ConnectionResetError:
                continue

    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        if recording and rec_start is not None and rec_data:
            print("Saving partial recording...")
            _save_csv(rec_data, session_dir)
    finally:
        sock.close()
        print("\nTotal packets received per board:")
        for ip, cnt in sorted(counters.items()):
            print(f"  {ip}: {cnt} packets")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    boards = discover_boards()
    if not boards:
        print("No boards found. Exiting.")
        sys.exit(1)
    stream_and_record(boards)
