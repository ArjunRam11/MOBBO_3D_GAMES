#!/usr/bin/env python3
"""
record_force_serial.py — MOBBO serial force recorder (non-blocking)

Reads the 7-value line the ESP32 prints each sample:
    f1,f2,f3,f4,COPx,COPy,W
e.g.  1.43,1.47,1.25,1.40,-0.60,0.96,5.55

Non-numeric lines (startup messages, "Frame rate: …") are silently ignored.

A dedicated reader thread drains the serial buffer continuously so the main
loop never blocks on I/O and key presses are always responsive.

Controls:
  S  — start 60-second recording
  T  — tare: zero each channel over the next 100 samples
  Q  — quit

Usage:
  python record_force_serial.py                   # auto-detect port, 60 s
  python record_force_serial.py --port COM3
  python record_force_serial.py --port COM3 --baud 115200 --duration 120
  python record_force_serial.py --plot ./recordings/serial_recording_20260401_130000

CSV columns:  time_s, f1_N, f2_N, f3_N, f4_N, W_N, copx_cm, copy_cm
  (identical layout to record_force.py — same plot function works on both)

Firmware line to add in loop() (after computing forces + CoP):
  Serial.printf("%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\\n",
                f1.fval, f2.fval, f3.fval, f4.fval,
                COPx.fval, COPy.fval, W.fval);
"""

import serial
import serial.tools.list_ports
import time
import csv
import os
import json
import threading
import queue
import argparse
from datetime import datetime
from collections import deque

DEFAULT_BAUD    = 115200
RECORD_DURATION = 60
TARE_SAMPLES    = 100


# ── Auto-detect port ──────────────────────────────────────────────────────────

def _auto_detect_port():
    keywords = ("cp210", "ch340", "ch341", "ftdi", "esp", "arduino", "usb serial")
    for p in serial.tools.list_ports.comports():
        if any(kw in (p.description or "").lower() for kw in keywords):
            return p.device
    ports = serial.tools.list_ports.comports()
    return ports[0].device if ports else None


# ── Serial reader thread ──────────────────────────────────────────────────────

class _SerialReader(threading.Thread):
    """
    Continuously reads lines from serial and parses them.
    Accepts lines with exactly 7 comma-separated floats:
        f1, f2, f3, f4, COPx, COPy, W
    Valid tuples are pushed into out_q.
    Oldest item is dropped if the consumer falls behind.
    """
    def __init__(self, ser, out_q, stop_event):
        super().__init__(daemon=True)
        self._ser  = ser
        self._q    = out_q
        self._stop = stop_event

    def run(self):
        while not self._stop.is_set():
            try:
                raw = self._ser.readline()
            except serial.SerialException:
                break
            if not raw:
                continue
            line  = raw.decode("ascii", errors="ignore").strip()
            parts = line.split(",")
            if len(parts) != 7:
                continue
            try:
                vals = tuple(float(p) for p in parts)
            except ValueError:
                continue
            if self._q.full():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    pass
            self._q.put_nowait(vals)


# ── Keyboard listener thread ──────────────────────────────────────────────────

class _KeyListener(threading.Thread):
    def __init__(self, key_q, stop_event):
        super().__init__(daemon=True)
        self._q    = key_q
        self._stop = stop_event

    def run(self):
        try:
            import msvcrt
            while not self._stop.is_set():
                if msvcrt.kbhit():
                    ch = msvcrt.getwch().upper()
                    if   ch == "S": self._q.put_nowait("start")
                    elif ch == "T": self._q.put_nowait("tare")
                    elif ch == "Q": self._q.put_nowait("quit")
                time.sleep(0.01)
        except ImportError:
            try:
                import keyboard as kb
                _s_held = False
                while not self._stop.is_set():
                    if kb.is_pressed("s") and not _s_held:
                        self._q.put_nowait("start"); _s_held = True
                    elif not kb.is_pressed("s"):
                        _s_held = False
                    if kb.is_pressed("t"):
                        self._q.put_nowait("tare"); time.sleep(0.3)
                    if kb.is_pressed("q"):
                        self._q.put_nowait("quit")
                    time.sleep(0.01)
            except ImportError:
                pass


# ── Main recorder ─────────────────────────────────────────────────────────────

class SerialForceRecorder:
    def __init__(self, port, baud, duration, out_dir):
        self.port        = port
        self.baud        = baud
        self.duration    = duration
        self.out_dir     = out_dir
        self.session_dir = None

    def run(self):
        port = self.port or _auto_detect_port()
        if port is None:
            print("No serial port found. Use --port COM?")
            return None
        if self.port is None:
            print(f"Auto-detected port: {port}")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.out_dir, f"serial_recording_{stamp}")
        os.makedirs(self.session_dir, exist_ok=True)

        print()
        print("=" * 62)
        print("  MOBBO Serial Force Recorder  (f1,f2,f3,f4,COPx,COPy,W)")
        print(f"  Port     : {port}  @{self.baud} baud")
        print(f"  Duration : {self.duration} s  (after S pressed)")
        print(f"  Output   : {self.session_dir}")
        print("=" * 62)

        try:
            ser = serial.Serial(port=port, baudrate=self.baud, timeout=0.1)
        except serial.SerialException as e:
            print(f"Cannot open {port}: {e}")
            return None

        time.sleep(0.1)
        ser.reset_input_buffer()

        stop_event = threading.Event()
        data_q     = queue.Queue(maxsize=2000)
        key_q      = queue.Queue()

        _SerialReader(ser, data_q, stop_event).start()
        _KeyListener(key_q, stop_event).start()

        print("\n  S = start recording   T = tare   Q = quit")
        print("-" * 62)
        print("  Waiting for S…", flush=True)

        # ── Per-session state ─────────────────────────────────────────────────
        recording      = False
        t_end          = None
        rec_start_wall = None
        fh = writer = csv_path = None

        # Tare: one offset per channel
        tare_offset  = [0.0] * 4
        tare_buf     = [[] for _ in range(4)]
        taring       = False

        # 3-sample median filter: one ring buffer per channel
        filter_buf   = [deque([0.0, 0.0, 0.0], maxlen=3) for _ in range(4)]
        filter_ready = 0

        rate_counter   = 0
        last_status_ts = time.time()
        last_ft        = [0.0] * 4
        last_W         = 0.0
        packet_count   = 0

        try:
            while not stop_event.is_set():

                # ── Key events ────────────────────────────────────────────────
                try:
                    key = key_q.get_nowait()
                    if key == "quit":
                        print("\nQ — quitting.")
                        break

                    elif key == "start" and not recording:
                        # Flush stale buffered data before starting
                        while not data_q.empty():
                            try: data_q.get_nowait()
                            except queue.Empty: break
                        recording      = True
                        t_end          = time.time() + self.duration
                        rec_start_wall = time.time()
                        safe     = port.replace("\\","_").replace("/","_").replace(":","")
                        csv_path = os.path.join(self.session_dir, f"serial_{safe}.csv")
                        fh       = open(csv_path, "w", newline="", buffering=1)
                        writer   = csv.writer(fh)
                        writer.writerow(["time_s", "f1_N", "f2_N", "f3_N", "f4_N",
                                         "W_N", "copx_cm", "copy_cm"])
                        print(f"\n  Recording started — {self.duration} s"
                              f"  ->  {os.path.basename(csv_path)}", flush=True)

                    elif key == "start" and recording:
                        print("\n  Already recording…", flush=True)

                    elif key == "tare":
                        tare_buf = [[] for _ in range(4)]
                        taring   = True
                        print("\nTARE started — collecting 100 samples…", flush=True)

                except queue.Empty:
                    pass

                # ── Stop when duration expires ────────────────────────────────
                if recording and time.time() >= t_end:
                    print(f"\n  {self.duration} s elapsed — recording stopped.")
                    break

                # ── Get next sample (non-blocking) ────────────────────────────
                try:
                    f1, f2, f3, f4, copx, copy, _ = data_q.get_nowait()
                except queue.Empty:
                    time.sleep(0.001)
                    continue

                wall_time = time.time()
                forces    = [f1, f2, f3, f4]

                # ── Tare per channel ──────────────────────────────────────────
                if taring:
                    for ch in range(4):
                        tare_buf[ch].append(forces[ch])
                    if len(tare_buf[0]) >= TARE_SAMPLES:
                        tare_offset = [sum(tare_buf[ch]) / len(tare_buf[ch])
                                       for ch in range(4)]
                        taring = False
                        print(
                            f"\nTare done:  "
                            f"f1={tare_offset[0]:+.3f}  f2={tare_offset[1]:+.3f}  "
                            f"f3={tare_offset[2]:+.3f}  f4={tare_offset[3]:+.3f}  N",
                            flush=True,
                        )

                # ── 3-sample median filter per channel ────────────────────────
                for ch in range(4):
                    filter_buf[ch].append(forces[ch])
                if filter_ready < 3:
                    filter_ready += 1
                    continue

                ft  = [sorted(filter_buf[ch])[1] - tare_offset[ch] for ch in range(4)]
                W_t = sum(ft)

                last_ft = ft
                last_W  = W_t
                packet_count += 1
                rate_counter += 1

                # ── Write CSV ─────────────────────────────────────────────────
                if recording:
                    writer.writerow([
                        f"{wall_time - rec_start_wall:.6f}",
                        f"{ft[0]:.4f}", f"{ft[1]:.4f}",
                        f"{ft[2]:.4f}", f"{ft[3]:.4f}",
                        f"{W_t:.4f}",
                        f"{copx:.4f}", f"{copy:.4f}",
                    ])

                # ── Live status every 1 s ─────────────────────────────────────
                now = time.time()
                if now - last_status_ts >= 1.0:
                    hz        = rate_counter / (now - last_status_ts)
                    remaining = max(0.0, t_end - now) if recording else 0.0
                    rec_tag   = f"  REC {remaining:.0f}s left" if recording else "  (idle)"
                    tare_tag  = "  TARING" if taring else ""
                    print(
                        f"\r  {hz:5.0f} Hz | "
                        f"f1={last_ft[0]:+6.2f} f2={last_ft[1]:+6.2f} "
                        f"f3={last_ft[2]:+6.2f} f4={last_ft[3]:+6.2f} N | "
                        f"W={last_W:.2f} N"
                        f"{rec_tag}{tare_tag}   ",
                        end="", flush=True,
                    )
                    rate_counter   = 0
                    last_status_ts = now

        except KeyboardInterrupt:
            print("\nInterrupted")
        finally:
            stop_event.set()
            if fh:
                fh.flush()
                fh.close()
            ser.close()

        print(f"\n\nDone — {packet_count} samples")
        print(f"  Output : {self.session_dir}")

        if csv_path:
            meta = {
                "timestamp"   : stamp,
                "port"        : port,
                "baud"        : self.baud,
                "duration_s"  : self.duration,
                "samples"     : packet_count,
                "tare_N"      : {f"f{i+1}": round(tare_offset[i], 4) for i in range(4)},
                "columns"     : ["time_s","f1_N","f2_N","f3_N","f4_N",
                                 "W_N","copx_cm","copy_cm"],
            }
            with open(os.path.join(self.session_dir, "session_info.json"), "w") as mf:
                json.dump(meta, mf, indent=2)

        return self.session_dir


# ── Plot — identical layout to record_force.py ────────────────────────────────

def plot_session(session_dir: str):
    """
    Plot f1..f4 and W from a serial recording session.

    Top   : f1, f2, f3, f4 overlaid vs time
    Bottom: W (total weight) vs time

    Same layout as record_force.py — works on board_*.csv files too.
    """
    import csv as _csv, glob

    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("matplotlib not installed — run: pip install matplotlib")
        return

    # Accept serial_*.csv (this script) or board_*.csv (record_force.py)
    csv_paths = (sorted(glob.glob(os.path.join(session_dir, "serial_*.csv"))) or
                 sorted(glob.glob(os.path.join(session_dir, "board_*.csv"))))
    if not csv_paths:
        print(f"No CSV files found in {session_dir}")
        return

    for csv_path in csv_paths:
        t, f1, f2, f3, f4, W = [], [], [], [], [], []

        with open(csv_path, newline="") as fh:
            for row in _csv.DictReader(fh):
                try:
                    t.append(float(row["time_s"]))
                    f1.append(float(row["f1_N"]))
                    f2.append(float(row["f2_N"]))
                    f3.append(float(row["f3_N"]))
                    f4.append(float(row["f4_N"]))
                    W.append(float(row["W_N"]))
                except (ValueError, KeyError):
                    continue

        if not t:
            print(f"No data in {csv_path}")
            continue

        label = os.path.splitext(os.path.basename(csv_path))[0]
        fig   = plt.figure(figsize=(14, 7))
        fig.suptitle(f"Force Recording — {label}", fontsize=12)
        gs    = gridspec.GridSpec(2, 1, hspace=0.35)

        ax_f = fig.add_subplot(gs[0])
        ax_f.plot(t, f1, lw=0.8, label="f1")
        ax_f.plot(t, f2, lw=0.8, label="f2")
        ax_f.plot(t, f3, lw=0.8, label="f3")
        ax_f.plot(t, f4, lw=0.8, label="f4")
        ax_f.axhline(0, color="black", lw=0.5, ls="--")
        ax_f.set_ylabel("Force (N)")
        ax_f.set_title("Individual channels  (median-filtered, tared)")
        ax_f.legend(loc="upper right", ncol=4, fontsize=8)
        ax_f.grid(True, alpha=0.3)

        ax_w = fig.add_subplot(gs[1], sharex=ax_f)
        ax_w.plot(t, W, color="tab:purple", lw=0.9, label="W = f1+f2+f3+f4")
        ax_w.axhline(0, color="black", lw=0.5, ls="--")
        ax_w.set_xlabel("Time (s)")
        ax_w.set_ylabel("Weight (N)")
        ax_w.set_title("Total weight")
        ax_w.legend(loc="upper right", fontsize=8)
        ax_w.grid(True, alpha=0.3)

        plt.tight_layout()

    plt.show()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="MOBBO serial recorder — reads f1,f2,f3,f4,COPx,COPy,W from UART")
    ap.add_argument("--port",     type=str, default=None,
                    help="Serial port (e.g. COM3). Auto-detects if omitted.")
    ap.add_argument("--baud",     type=int, default=DEFAULT_BAUD,
                    help=f"Baud rate (default: {DEFAULT_BAUD})")
    ap.add_argument("--duration", type=int, default=RECORD_DURATION,
                    help=f"Recording duration in seconds (default: {RECORD_DURATION})")
    ap.add_argument("--out",      type=str, default="./recordings",
                    help="Output directory (default: ./recordings)")
    ap.add_argument("--plot",     type=str, default=None, metavar="SESSION_DIR",
                    help="Plot a previously recorded session and exit")
    args = ap.parse_args()

    if args.plot:
        plot_session(args.plot)
        return

    rec = SerialForceRecorder(
        port=args.port, baud=args.baud,
        duration=args.duration, out_dir=args.out,
    )
    session_dir = rec.run()

    if session_dir:
        ans = input("\nPlot results now? [y/N] ").strip().lower()
        if ans == "y":
            plot_session(session_dir)


if __name__ == "__main__":
    main()
