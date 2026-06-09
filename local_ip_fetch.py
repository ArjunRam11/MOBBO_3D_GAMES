import socket

class Ip:
    def __init__(self):
        self.Local = None
        self.Broadcast = None
        self.Ip = []
        self.get_local_ip()

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]  # Fetch local IP address
            s.close()

            # Calculate the broadcast address (set last octet to 255)
            broadcast_address = self.calculate_broadcast(ip_address)

            # Store addresses
            self.Local = ip_address
            self.Broadcast = broadcast_address
            self.Ip.append(self.Broadcast)
            return ip_address, broadcast_address
        except Exception as e:
            # Fallback: try to find a usable local interface without external connectivity
            try:
                import socket as _s
                for iface_ip in _s.gethostbyname_ex(_s.gethostname())[2]:
                    if not iface_ip.startswith("127."):
                        broadcast_address = self.calculate_broadcast(iface_ip)
                        self.Local = iface_ip
                        self.Broadcast = broadcast_address
                        self.Ip.append(self.Broadcast)
                        return iface_ip, broadcast_address
            except Exception:
                pass
            # Last resort: use loopback so the app can still start
            self.Local = "127.0.0.1"
            self.Broadcast = "127.0.0.1"
            self.Ip.append("127.0.0.1")
            return "127.0.0.1", "127.0.0.1"

    def calculate_broadcast(self, ip_address):
        # Replace the last octet with 255
        octets = ip_address.split('.')
        octets[-1] = '255'  # Replace the last octet
        return '.'.join(octets)

    def Local_ip(self):
        return self.Ip




if __name__=='__main__':
    ip_fetcher = Ip()
    local_ip = ip_fetcher.Local  # Local IP address
    broadcast_ip = ip_fetcher.Broadcast  # Broadcast IP address
    print(f"Local IP: {local_ip}")
    print(f"Broadcast IP: {broadcast_ip}")
