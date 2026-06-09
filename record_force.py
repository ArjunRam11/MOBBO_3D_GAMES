#!/usr/bin/env python3
"""
record_force.py — MOBBO raw force recorder (1 board or multi-board)

Records all 4 load cell channels over UDP for a configurable duration.
Saves: time_s, f1_N, f2_N, f3_N, f4_N, W_N, copx_cm, copy_cm

Controls:
  S  — start 60-second recording
  T  — tare: collect 100 samples per board, store mean as zero offset
  Q  — quit / stop early

Usage:
  python record_force.py                  # wait for S, 60 s, output in ./recordings/
  python record_force.py --duration 120   # 2 min
  python record_force.py --out C:/data    # custom output folder
  python record_force.py --plot ./recordings/force_recording_20260401_120000
"""

import socket
import struct
import time
import csv
import os
import json
import threading
import argparse
import queue
from datetime import datetime
from collections import deque

# ─────────────────────────────────────────────────────────────────────────────
BOARD_UDP_PORT  = 23000
DISCOVERY_MSG   = b"Hey!mobbos"
RECORD_DURATION = 10     # seconds
TARE_SAMPLES    = 100    # packets averaged per tare
# ─────────────────────────────────────────────────────────────────────────────


class BoardState:
    def __init__(self, ip: str):
        self.ip             = ip
        self.offset         = [0.0, 0.0, 0.0, 0.0]
        self.tare_buf       = [[] for _ in range(4)]
        self.taring         = False
        self.packet_count   = 0
        self.last_rate_time = 0.0
        self.rate_counter   = 0
        # 3-sample median filter — eliminates single-sample ADC spikes
        self.filter_buf     = [deque([0.0, 0.0, 0.0], maxlen=3) for _ in range(4)]
        self.filter_ready   = 0   # counts up to 3, then stays at 3


class ForceRecorder:
    def __init__(self, duration: int = RECORD_DURATION, out_dir: str = "./recordings"):
        self.duration    = duration
        self.out_dir     = out_dir
        self.boards      = {}
        self.csv_files   = {}
        self.lock        = threading.Lock()
        self.tare_queue  = queue.Queue()
        self.key_queue   = queue.Queue()   # "start" | "quit"
        self.stop_event  = threading.Event()
        self.session_dir = None

    # ── Socket helpers ────────────────────────────────────────────────────────

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "192.168.0.255"

    def _broadcast_discovery(self, sock: socket.socket):
        local_ip = self._get_local_ip()
        subnet   = local_ip.rsplit(".", 1)[0] + ".255"
        for target in (subnet, "255.255.255.255"):
            try:
                sock.sendto(DISCOVERY_MSG, (target, BOARD_UDP_PORT))
            except OSError:
                pass

    # ── CSV ───────────────────────────────────────────────────────────────────

    def _open_csv(self, ip: str):
        safe = ip.replace(".", "_")
        path = os.path.join(self.session_dir, f"board_{safe}.csv")
        fh   = open(path, "w", newline="")
        w    = csv.writer(fh)
        w.writerow(["time_s", "f1_N", "f2_N", "f3_N", "f4_N", "W_N", "copx_cm", "copy_cm"])
        self.csv_files[ip] = (fh, w)
        print(f"  Logging {ip}  ->  {os.path.basename(path)}")

    # ── Tare ──────────────────────────────────────────────────────────────────

    def _trigger_tare(self):
        with self.lock:
            for bs in self.boards.values():
                bs.tare_buf = [[] for _ in range(4)]
                bs.taring   = True
        print("\nTARE started — collecting 100 samples per board…")

    def _update_tare(self, bs: BoardState, forces: list):
        if not bs.taring:
            return
        for ch in range(4):
            bs.tare_buf[ch].append(forces[ch])
        if len(bs.tare_buf[0]) >= TARE_SAMPLES:
            bs.offset = [
                sum(bs.tare_buf[ch]) / len(bs.tare_buf[ch])
                for ch in range(4)
            ]
            bs.taring = False
            print(
                f"\nTare done [{bs.ip}]:  "
                f"f1={bs.offset[0]:+.3f}  f2={bs.offset[1]:+.3f}  "
                f"f3={bs.offset[2]:+.3f}  f4={bs.offset[3]:+.3f}  N"
            )

    # ── Packet parsing ────────────────────────────────────────────────────────

    @staticmethod
    def _xor_ok(data: bytes) -> bool:
        """Verify XOR checksum: status3 (data[3]) == XOR of data[4:]."""
        if len(data) < 5:
            return False
        computed = 0
        for b in data[4:]:
            computed ^= b
        return computed == data[3]

    def _parse_packet(self, data: bytes):
        """Returns (f1, f2, f3, f4, copx, copy) or None. Drops corrupted packets."""
        if not self._xor_ok(data):
            return None

        if len(data) == 32:
            try:
                vals = struct.unpack('4c7f', data)
                F = vals[4:]
                if 0.0 <= F[0] <= 86400.0 and abs(F[5]) <= 1000.0:
                    # Game format: F0=timestamp, F1..F4=forces, F5=COPx, F6=COPy
                    return F[1], F[2], F[3], F[4], F[5], F[6]
                else:
                    # Display format: F0..F3=forces, F4=COPx, F5=COPy, F6=W
                    return F[0], F[1], F[2], F[3], F[4], F[5]
            except struct.error:
                return None

        elif len(data) == 34:
            try:
                vals = struct.unpack('4c7fh', data)
                F = vals[4:11]
                return F[0], F[1], F[2], F[3], F[4], F[5]
            except struct.error:
                return None

        elif len(data) == 36:
            try:
                vals = struct.unpack('4c8f', data)
                F = vals[4:]
                return F[1], F[2], F[3], F[4], F[5], F[6]
            except struct.error:
                return None

        return None

    # ── Keyboard listener ─────────────────────────────────────────────────────

    def _keyboard_listener(self):
        """Non-blocking key watcher.  S=start  T=tare  Q=quit"""
        try:
            import msvcrt
            while not self.stop_event.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getwch().upper()
                    if ch == 'S':
                        self.key_queue.put("start")
                    elif ch == 'T':
                        self.tare_queue.put("tare")
                    elif ch == 'Q':
                        self.key_queue.put("quit")
                time.sleep(0.02)
        except ImportError:
            try:
                import keyboard as kb
                _s_down = False
                while not self.stop_event.is_set():
                    if kb.is_pressed('s') and not _s_down:
                        self.key_queue.put("start")
                        _s_down = True
                    elif not kb.is_pressed('s'):
                        _s_down = False
                    if kb.is_pressed('t'):
                        self.tare_queue.put("tare")
                        time.sleep(0.4)
                    if kb.is_pressed('q'):
                        self.key_queue.put("quit")
                    time.sleep(0.02)
            except ImportError:
                print("No keyboard library — press Ctrl+C to quit")

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.out_dir, f"force_recording_{stamp}")
        os.makedirs(self.session_dir, exist_ok=True)

        print()
        print("=" * 58)
        print("  MOBBO Force Recorder")
        print(f"  Duration  : {self.duration} s  (after S pressed)")
        print(f"  Output    : {self.session_dir}")
        print(f"  Port      : {BOARD_UDP_PORT}")
        print("=" * 58)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", BOARD_UDP_PORT))
        sock.settimeout(0.5)

        print("\nBroadcasting discovery…")
        for _ in range(3):
            self._broadcast_discovery(sock)
            time.sleep(0.15)

        kb_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        kb_thread.start()

        print("\n  S = start recording   T = tare   Q = quit")
        print("-" * 58)
        print("  Waiting for S…", flush=True)

        # ── Phase 1: idle — receive packets, tare, wait for S ────────────────
        recording      = False
        t_start        = None
        t_end          = None
        rec_start_wall = None
        last_resend    = time.time()

        try:
            while not self.stop_event.is_set():

                # Drain key events
                try:
                    key = self.key_queue.get_nowait()
                    if key == "quit":
                        print("\nQ — quitting.")
                        break
                    elif key == "start" and not recording:
                        recording      = True
                        t_start        = time.time()
                        t_end          = t_start + self.duration
                        rec_start_wall = t_start
                        print(f"\n  Recording started — {self.duration} s", flush=True)
                    elif key == "start" and recording:
                        print("\n  Already recording…", flush=True)
                except queue.Empty:
                    pass

                # Drain tare requests
                try:
                    self.tare_queue.get_nowait()
                    self._trigger_tare()
                except queue.Empty:
                    pass

                # Stop when duration expires
                if recording and time.time() >= t_end:
                    print(f"\n  {self.duration} s elapsed — recording stopped.")
                    break

                # Resend discovery every 5 s
                if time.time() - last_resend > 5.0:
                    self._broadcast_discovery(sock)
                    last_resend = time.time()

                # Receive packet
                try:
                    data, addr = sock.recvfrom(512)
                except socket.timeout:
                    continue
                except OSError:
                    continue

                ip        = addr[0]
                wall_time = time.time()

                # Register new board
                with self.lock:
                    if ip not in self.boards:
                        self.boards[ip] = BoardState(ip)
                        if recording:
                            self._open_csv(ip)
                        print(f"\n  Board discovered: {ip}")
                        try:
                            sock.sendto(DISCOVERY_MSG, (ip, BOARD_UDP_PORT))
                        except OSError:
                            pass

                parsed = self._parse_packet(data)
                if parsed is None:
                    continue

                f1, f2, f3, f4, copx, copy = parsed
                forces = [f1, f2, f3, f4]

                ft = None   # tared + filtered forces (set once buffer is full)
                W_t = None

                with self.lock:
                    bs = self.boards[ip]
                    self._update_tare(bs, forces)

                    # Push raw sample into each channel's 3-slot ring buffer
                    for ch in range(4):
                        bs.filter_buf[ch].append(forces[ch])
                    if bs.filter_ready < 3:
                        bs.filter_ready += 1

                    # Compute median-of-3, then subtract tare offset
                    if bs.filter_ready == 3:
                        ff  = [sorted(bs.filter_buf[ch])[1] for ch in range(4)]
                        ft  = [ff[ch] - bs.offset[ch] for ch in range(4)]
                        W_t = sum(ft)

                    bs.packet_count += 1
                    bs.rate_counter += 1

                # Skip until the 3-sample buffer is primed
                if ft is None:
                    continue

                # Write CSV only while recording
                if recording:
                    if ip not in self.csv_files:
                        self._open_csv(ip)
                    rel_time = wall_time - rec_start_wall
                    _, writer = self.csv_files[ip]
                    writer.writerow([
                        f"{rel_time:.6f}",
                        f"{ft[0]:.4f}", f"{ft[1]:.4f}", f"{ft[2]:.4f}", f"{ft[3]:.4f}",
                        f"{W_t:.4f}",
                        f"{copx:.4f}", f"{copy:.4f}",
                    ])

                # Live status every 2 s (shows tared + filtered values)
                now = time.time()
                with self.lock:
                    if now - bs.last_rate_time >= 2.0:
                        dt        = now - bs.last_rate_time if bs.last_rate_time > 0 else 2.0
                        rate      = bs.rate_counter / dt
                        remaining = max(0.0, t_end - now) if recording else 0.0
                        rec_tag   = f"  REC {remaining:.0f}s left" if recording else "  (idle)"
                        tare_tag  = "  TARING" if bs.taring else ""
                        print(
                            f"\r  [{ip}]  {rate:4.0f} Hz | "
                            f"f1={ft[0]:+7.2f} f2={ft[1]:+7.2f} "
                            f"f3={ft[2]:+7.2f} f4={ft[3]:+7.2f} N | "
                            f"W={W_t:.1f}N{rec_tag}{tare_tag}",
                            end="", flush=True,
                        )
                        bs.rate_counter   = 0
                        bs.last_rate_time = now

        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            self.stop_event.set()
            for ip, (fh, _) in self.csv_files.items():
                fh.close()
            sock.close()

        print(f"\n\nRecording complete!")
        print(f"  Boards : {list(self.boards.keys())}")

        meta = {
            "timestamp"     : stamp,
            "duration_s"    : self.duration,
            "boards"        : list(self.boards.keys()),
            "packet_counts" : {ip: bs.packet_count for ip, bs in self.boards.items()},
            "columns"       : ["time_s", "f1_N", "f2_N", "f3_N", "f4_N", "W_N", "copx_cm", "copy_cm"],
        }
        with open(os.path.join(self.session_dir, "session_info.json"), "w") as f:
            json.dump(meta, f, indent=2)
        print(f"  Output : {self.session_dir}")

        return self.session_dir


# ─────────────────────────────────────────────────────────────────────────────
# PLOT
# ─────────────────────────────────────────────────────────────────────────────

def plot_session(session_dir: str):
    """
    Plot force channels and total weight from a recorded session.

    Reads all board_*.csv files in session_dir and produces one figure
    per board with two stacked subplots:
      - Top   : f1, f2, f3, f4  vs time (N)
      - Bottom: W (total weight) vs time (N)

    Usage:
        plot_session("./recordings/force_recording_20260401_120000")
    or:
        python record_force.py --plot ./recordings/force_recording_20260401_120000
    """
    import csv as _csv
    import glob

    try:
        import matplotlib
        matplotlib.use("TkAgg")          # change to "Qt5Agg" if TkAgg unavailable
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("matplotlib not installed — run: pip install matplotlib")
        return

    csv_paths = sorted(glob.glob(os.path.join(session_dir, "board_*.csv")))
    if not csv_paths:
        print(f"No board_*.csv files found in {session_dir}")
        return

    for csv_path in csv_paths:
        t, f1, f2, f3, f4, W, cx, cy = [], [], [], [], [], [], [], []

        with open(csv_path, newline="") as fh:
            reader = _csv.DictReader(fh)
            for row in reader:
                try:
                    t.append(float(row["time_s"]))
                    f1.append(float(row["f1_N"]))
                    f2.append(float(row["f2_N"]))
                    f3.append(float(row["f3_N"]))
                    f4.append(float(row["f4_N"]))
                    W.append(float(row["W_N"]))
                    cx.append(float(row["copx_cm"]))
                    cy.append(float(row["copy_cm"]))
                except (ValueError, KeyError):
                    continue

        if not t:
            print(f"No data rows in {csv_path}")
            continue

        board_label = os.path.splitext(os.path.basename(csv_path))[0]

        fig = plt.figure(figsize=(14, 7))
        fig.suptitle(f"Force Recording — {board_label}", fontsize=12)

        gs = gridspec.GridSpec(2, 1, hspace=0.35)
        ax_f = fig.add_subplot(gs[0])
        ax_w = fig.add_subplot(gs[1], sharex=ax_f)

        # ── Top: individual channels ──────────────────────────────────────────
        ax_f.plot(t, f1, lw=0.8, label="f1")
        ax_f.plot(t, f2, lw=0.8, label="f2")
        ax_f.plot(t, f3, lw=0.8, label="f3")
        ax_f.plot(t, f4, lw=0.8, label="f4")
        ax_f.axhline(0, color="black", lw=0.5, ls="--")
        ax_f.set_ylabel("Force (N)")
        ax_f.set_title("Individual channels")
        ax_f.legend(loc="upper right", ncol=4, fontsize=8)
        ax_f.grid(True, alpha=0.3)

        # ── Bottom: total weight ──────────────────────────────────────────────
        ax_w.plot(t, W, color="tab:purple", lw=0.9, label="W = f1+f2+f3+f4")
        ax_w.axhline(0, color="black", lw=0.5, ls="--")
        ax_w.set_xlabel("Time (s)")
        ax_w.set_ylabel("Weight (N)")
        ax_w.set_title("Total weight")
        ax_w.legend(loc="upper right", fontsize=8)
        ax_w.grid(True, alpha=0.3)

        plt.tight_layout()

    plt.show()


# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="MOBBO raw force recorder")
    ap.add_argument("--duration", type=int, default=RECORD_DURATION,
                    help=f"Recording duration in seconds (default: {RECORD_DURATION})")
    ap.add_argument("--out", type=str, default="./recordings",
                    help="Parent output directory (default: ./recordings)")
    ap.add_argument("--plot", type=str, default=None, metavar="SESSION_DIR",
                    help="Plot a previously recorded session and exit")
    args = ap.parse_args()

    if args.plot:
        plot_session(args.plot)
        return

    rec = ForceRecorder(duration=args.duration, out_dir=args.out)
    session_dir = rec.run()

    if session_dir and rec.csv_files:
        answer = input("\nPlot results now? [y/N] ").strip().lower()
        if answer == "y":
            plot_session(session_dir)





if __name__ == "__main__":
    main()
