"""
diagnose_udp.py — Run this on the PC while the ESP32 board is powered on.
It prints exactly what's happening with the broadcast and responses.
"""
import socket
import time

# Step 1: Find our broadcast address
from local_ip_fetch import Ip
ip = Ip()
local_ip = ip.Local
broadcast_ip = ip.Broadcast
print(f"[1] Local IP:     {local_ip}")
print(f"[2] Broadcast IP: {broadcast_ip}")
print(f"[3] Sending discovery to {broadcast_ip}:23000")
print()

# Step 2: Send discovery and listen
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(2)

MESSAGE = "Hey!mobbos"

print(f"[4] Sending '{MESSAGE}' (3 attempts, 2s timeout each)...")
print("    Watch the ESP32 serial monitor for [DISCOVERY] lines!")
print()

for attempt in range(1, 4):
    print(f"--- Attempt {attempt} ---")
    try:
        sock.sendto(MESSAGE.encode(), (broadcast_ip, 23000))
        print(f"  Sent {len(MESSAGE)} bytes to {broadcast_ip}:23000")
    except Exception as e:
        print(f"  SEND FAILED: {e}")
        continue

    # Try to receive multiple responses (multiple boards)
    recv_start = time.time()
    while time.time() - recv_start < 2:
        try:
            data, addr = sock.recvfrom(2048)
            print(f"  RECEIVED {len(data)} bytes from {addr[0]}:{addr[1]}")
            print(f"  Raw hex: {data.hex()}")
            
            # Check if it's our own broadcast echoed back
            if data == MESSAGE.encode():
                print(f"  ^ This is our own broadcast echoed back (ignore)")
            else:
                print(f"  ^ THIS IS A BOARD RESPONSE!")
        except socket.timeout:
            print(f"  No response (timeout after 2s)")
            break
    print()

sock.close()

# Step 3: Also try sending directly to a known board IP
board_ip = input("Enter a board IP to test directly (e.g. 192.168.0.113), or press Enter to skip: ").strip()
if board_ip:
    print(f"\n[5] Sending directly to {board_ip}:23000...")
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock2.settimeout(6)
    try:
        sock2.sendto(MESSAGE.encode(), (board_ip, 23000))
        print(f"  Sent. Waiting for response...")
        data, addr = sock2.recvfrom(2048)
        print(f"  RECEIVED {len(data)} bytes from {addr[0]}:{addr[1]}")
        print(f"  Raw hex: {data.hex()}")
        print(f"  THIS WORKS! The board responds to direct UDP.")
    except socket.timeout:
        print(f"  No response from {board_ip} (timeout)")
        print(f"  Board may not be running or firewall is blocking.")
    except Exception as e:
        print(f"  Error: {e}")
    sock2.close()

print("\nDone.")