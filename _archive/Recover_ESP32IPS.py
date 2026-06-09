"""
mobbo_discover.py  —  MOBBO ESP32 board discovery  (dual-strategy)

ROOT CAUSE ANALYSIS — why 0x80 broadcast only got 1 board
===========================================================
When ESP32 WiFiUDP receives a BROADCAST packet, udpClient.remoteIP()
returns the BROADCAST address (192.168.0.255), NOT your machine's IP.

So SendRegistrationRequest() does:
    udpClient.beginPacket(192.168.0.255, <your_port>)
which either fails silently or goes to broadcast. Your ephemeral disc_sock
never sees it because it's not listening on the broadcast address.

Only ONE board replied because that board had your unicast IP already
cached in serverIP from a previous session's REGISTER exchange.

THE FIX: UNICAST 0x80 to every host in the subnet
===================================================
Unicast 0x80 to 192.168.0.X  →  board receives it
    cmd = 0x80 & 0xF0 = 0x80  →  REGISTER case fires
    serverIP   = YOUR real IP  (not broadcast — because you sent unicast)
    serverPort = YOUR ephemeral port
    SendRegistrationRequest() sends 32 bytes [0x00, 0x80, 0x00*30]
    directly back to your disc_sock  ✓

DISCOVERY PHASES
=================
  Phase 1  Passive (2 s)   — catch spontaneous startup broadcasts on :23000
  Phase 2  Broadcast ping  — "Hey!mobbos" to wake any sleeping boards
  Phase 3  Re-register     — unicast 0x80 to already-known boards
  Phase 4  Subnet sweep    — unicast 0x80 to EVERY host in /24
                             This is the phase that catches boards that
                             were already on before we started scanning
  Phase 5  Retry cycles    — keep sweeping until timeout or expected_count
"""

import socket
import time
import threading
import ipaddress


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
UDP_PORT      = 23000
REGISTER_CMD  = bytes([0x80])
DISCOVERY_MSG = b"Hey!mobbos"


def _own_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


OWN_IP = _own_ip()
print(f"[config] This machine's LAN IP : {OWN_IP}")

_net         = ipaddress.IPv4Network(f"{OWN_IP}/24", strict=False)
SUBNET_HOSTS = [str(h) for h in _net.hosts() if str(h) != OWN_IP]
print(f"[config] Subnet to sweep       : {_net}  ({len(SUBNET_HOSTS)} hosts)")


# ─────────────────────────────────────────────────────────────────────────────
# SHARED STATE
# ─────────────────────────────────────────────────────────────────────────────
known_addresses: set = set()
_lock                = threading.Lock()
_bg_thread           = None


def _register_ip(ip: str, source: str = ""):
    if ip == OWN_IP:
        return
    with _lock:
        if ip not in known_addresses:
            known_addresses.add(ip)
            tag = f"  ← {source}" if source else ""
            print(f"  [+] NEW board: {ip}  (total: {len(known_addresses)}){tag}")


def _snapshot() -> set:
    with _lock:
        return set(known_addresses) - {OWN_IP}


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND LISTENER  (port 23000)
# Catches spontaneous startup broadcasts from boards that just powered on.
# ─────────────────────────────────────────────────────────────────────────────
def _background_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass  # Windows — fine, SO_REUSEPORT not needed
    sock.bind(("", UDP_PORT))
    sock.settimeout(1.0)
    print(f"[bg ] Listener on port {UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(256)
            _register_ip(addr[0], source="startup-broadcast")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[bg ] error: {e}")


def _start_bg():
    global _bg_thread
    if _bg_thread and _bg_thread.is_alive():
        return
    _bg_thread = threading.Thread(target=_background_listener, daemon=True)
    _bg_thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# DRAIN  — read disc_sock for `window` seconds, never break on timeout
# ─────────────────────────────────────────────────────────────────────────────
def _drain(disc_sock: socket.socket, window: float, expected_count: int = None):
    deadline = time.time() + window
    while time.time() < deadline:
        try:
            data, addr = disc_sock.recvfrom(256)
            ip = addr[0]
            if ip != OWN_IP:
                _register_ip(ip, source=f"reply-port:{addr[1]}")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[drain] {e}")
        if expected_count and len(_snapshot()) >= expected_count:
            return


# ─────────────────────────────────────────────────────────────────────────────
# SUBNET SWEEP  — unicast REGISTER_CMD to every host
# ─────────────────────────────────────────────────────────────────────────────
def _unicast_sweep(disc_sock: socket.socket,
                   hosts: list,
                   batch_size: int = 25,
                   inter_batch_delay: float = 0.04):
    print(f"[sweep] Sending 0x80 unicast → {len(hosts)} hosts ...")
    for i in range(0, len(hosts), batch_size):
        batch = hosts[i: i + batch_size]
        for ip in batch:
            try:
                disc_sock.sendto(REGISTER_CMD, (ip, UDP_PORT))
            except Exception:
                pass
        time.sleep(inter_batch_delay)
    print("[sweep] Done.")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────
def get_available_ids(
    timeout: int        = 30,
    expected_count: int = 6,
) -> list | None:
    """
    Discover all reachable MOBBO ESP32 boards.

    Args:
        timeout        : Max scan time in seconds.
        expected_count : Stop early when this many boards are confirmed.

    Returns:
        Sorted list of IP strings, or None if nothing found.
    """
    _start_bg()
    time.sleep(0.5)

    disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    disc_sock.bind(("", 0))
    my_port = disc_sock.getsockname()[1]
    disc_sock.settimeout(0.05)

    print(f"\n[scan] disc_sock ephemeral port : {my_port}")
    print(f"[scan] Expected boards          : {expected_count}")
    print(f"[scan] Timeout                  : {timeout}s\n")

    t0 = time.time()

    def elapsed():
        return time.time() - t0

    def done():
        return (
            (expected_count and len(_snapshot()) >= expected_count)
            or elapsed() >= timeout
        )

    # ── Phase 1 : Passive harvest (2 s) ──────────────────────────────────
    print("── Phase 1 : Passive harvest (2 s) ─────────────────────────────")
    _drain(disc_sock, window=2.0, expected_count=expected_count)
    print(f"   {len(_snapshot())} board(s) found so far\n")
    if done():
        return _finish(disc_sock)

    # ── Phase 2 : Broadcast "Hey!mobbos" ─────────────────────────────────
    print("── Phase 2 : Broadcast 'Hey!mobbos' (3 bursts) ─────────────────")
    for i in range(3):
        disc_sock.sendto(DISCOVERY_MSG, ("<broadcast>", UDP_PORT))
        print(f"   burst {i+1} sent")
        time.sleep(0.02)
    _drain(disc_sock, window=1.5, expected_count=expected_count)
    print(f"   {len(_snapshot())} board(s) found so far\n")
    if done():
        return _finish(disc_sock)

    # ── Phase 3 : Re-register known boards ───────────────────────────────
    known_now = _snapshot()
    if known_now:
        print(f"── Phase 3 : Unicast 0x80 to {len(known_now)} known board(s) ──────────")
        for ip in known_now:
            disc_sock.sendto(REGISTER_CMD, (ip, UDP_PORT))
            print(f"   → {ip}")
        _drain(disc_sock, window=1.0, expected_count=expected_count)
        print(f"   {len(_snapshot())} board(s) found so far\n")
        if done():
            return _finish(disc_sock)

    # ── Phase 4 : Full subnet unicast sweep ───────────────────────────────
    # KEY PHASE: unicast 0x80 so remoteIP() = our real IP on each board,
    # guaranteeing SendRegistrationRequest() replies land on disc_sock.
    print("── Phase 4 : Full subnet unicast sweep ──────────────────────────")
    sweep_t = threading.Thread(
        target=_unicast_sweep,
        args=(disc_sock, SUBNET_HOSTS),
        kwargs={"batch_size": 25, "inter_batch_delay": 0.04},
        daemon=True,
    )
    sweep_t.start()

    sweep_deadline = time.time() + 15.0
    while time.time() < sweep_deadline and not done():
        _drain(disc_sock, window=0.5, expected_count=expected_count)
        print(f"   ... {len(_snapshot())}/{expected_count} confirmed  "
              f"(elapsed {elapsed():.1f}s)")

    sweep_t.join(timeout=2)
    print(f"   {len(_snapshot())} board(s) found after sweep\n")
    if done():
        return _finish(disc_sock)

    # ── Phase 5 : Retry cycles for stragglers ────────────────────────────
    print("── Phase 5 : Retry cycles ───────────────────────────────────────")
    cycle = 0
    while not done():
        cycle += 1
        print(f"   [retry {cycle}]  {len(_snapshot())}/{expected_count}  "
              f"elapsed={elapsed():.1f}s")
        for ip in _snapshot():
            disc_sock.sendto(REGISTER_CMD, (ip, UDP_PORT))
        _unicast_sweep(disc_sock, SUBNET_HOSTS,
                       batch_size=50, inter_batch_delay=0.02)
        _drain(disc_sock, window=2.0, expected_count=expected_count)

    return _finish(disc_sock)


def _finish(disc_sock: socket.socket) -> list | None:
    disc_sock.close()
    found = sorted(_snapshot())
    print("\n" + "═" * 50)
    if not found:
        print("  No boards found.")
        print("  Check: boards powered on? Same AP? Firewall blocking UDP 23000?")
        print("═" * 50)
        return None
    print(f"  Discovery complete — {len(found)} board(s):")
    for i, ip in enumerate(found, 1):
        print(f"    {i}. {ip}")
    print("═" * 50 + "\n")
    return found


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _start_bg()
    time.sleep(0.5)

    addresses = get_available_ids(timeout=30, expected_count=6)
    print(f"Final result: {addresses}")