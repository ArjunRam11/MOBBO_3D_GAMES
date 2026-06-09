"""
Test script for Godot Bridge
Run this to verify UDP communication is working before connecting to actual Godot
Supports both JSON and binary float32 formats
"""

import socket
import json
import time
import threading
import struct


class GodotReceiver:
    """Simple UDP receiver to test Godot Bridge"""

    def __init__(self, port=8000, data_format="binary"):
        self.port = port
        self.data_format = data_format
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(1.0)
        self.running = False
        self.packet_count = 0

    def start(self):
        """Start receiving data"""
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        print(f"🎮 Godot Receiver started on port {self.port} (format: {self.data_format})")
        print("Waiting for CoP data from MOBBO...\n")

    def _receive_loop(self):
        """Main receive loop"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                self.packet_count += 1

                if self.data_format == "json":
                    # Parse JSON data
                    json_data = json.loads(data.decode('utf-8'))
                    x = json_data.get('x', 0)
                    y = json_data.get('y', 0)
                    z = json_data.get('z', 0)
                    weight = json_data.get('weight', 0)
                    msg_code = json_data.get('type', 'unknown')

                else:  # binary format
                    # Unpack binary float32 array
                    floats = struct.unpack('4f', data)
                    msg_code = floats[0]
                    x = floats[1]
                    y = floats[2]
                    z = floats[3]
                    weight = 0  # Not included in binary format

                # Display data (every 10th packet to avoid spam)
                if self.packet_count % 10 == 0:
                    print(f"📦 Packet #{self.packet_count} from {addr}")
                    print(f"   ├─ Message Code: {msg_code}")
                    print(f"   ├─ X: {x:.4f} m")
                    print(f"   ├─ Y: {y:.4f} m")
                    print(f"   ├─ Z: {z:.4f} m")
                    if weight > 0:
                        print(f"   └─ Weight: {weight:.2f} N")
                    print()

            except socket.timeout:
                continue
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
            except struct.error as e:
                print(f"❌ Binary unpack error: {e}")
            except Exception as e:
                print(f"❌ Error: {e}")

    def stop(self):
        """Stop receiving data"""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        self.sock.close()
        print(f"\n✅ Received {self.packet_count} total packets")
        print("Godot Receiver stopped")


if __name__ == "__main__":
    print("=" * 60)
    print("🎮 MOBBO Godot Bridge - Test Receiver")
    print("=" * 60)
    print("\nThis simulates a Godot game receiving CoP data via UDP")
    print("Run your MOBBO main.py application to start sending data\n")

    # Use binary format on port 8000 for NOARK games
    receiver = GodotReceiver(port=8000, data_format="binary")

    try:
        receiver.start()

        # Keep running until user stops
        print("Press Ctrl+C to stop...\n")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping receiver...")
        receiver.stop()
        print("Goodbye!")
