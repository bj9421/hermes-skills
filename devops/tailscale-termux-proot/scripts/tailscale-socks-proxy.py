#!/usr/bin/env python3
"""TCP proxy: listen on PORT -> forward via SOCKS5 to TARGET:PORT"""
import socketserver, socket, struct, threading, sys

SOCKS5_HOST = "127.0.0.1"
SOCKS5_PORT = 1080
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9119
TARGET = sys.argv[2] if len(sys.argv) > 2 else "100.78.85.64"
TARGET_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else LISTEN_PORT
BUF_SIZE = 65536

def recvall(sock, n):
    """Read exactly n bytes from socket."""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data

def socks5_connect(dest_host, dest_port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    s.connect((SOCKS5_HOST, SOCKS5_PORT))
    # auth negotiation: no auth
    s.sendall(b"\x05\x01\x00")
    ver, method = recvall(s, 2)
    assert ver == 5, f"SOCKS5 bad version: {ver}"
    assert method == 0, f"SOCKS5 auth required: {method}"
    # connect request (IPv4)
    host_bytes = socket.inet_aton(dest_host)
    req = b"\x05\x01\x00\x01" + host_bytes + struct.pack(">H", dest_port)
    s.sendall(req)
    # response: VER REP RSV ATYP BND.ADDR BND.PORT
    resp = recvall(s, 10)
    rep = resp[1]
    assert rep == 0, f"SOCKS5 connect failed, status={rep}"
    return s

def pipe(src, dst, name=""):
    try:
        while True:
            data = src.recv(BUF_SIZE)
            if not data:
                break
            dst.sendall(data)
    except:
        pass
    finally:
        for s in (src, dst):
            try: s.close()
            except: pass

class ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        local = self.request
        local.settimeout(None)
        try:
            remote = socks5_connect(TARGET, TARGET_PORT)
        except Exception as e:
            try: local.close()
            except: pass
            return
        t1 = threading.Thread(target=pipe, args=(local, remote, "L->R"), daemon=True)
        t2 = threading.Thread(target=pipe, args=(remote, local, "R->L"), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()

if __name__ == "__main__":
    server = socketserver.ThreadingTCPServer(("0.0.0.0", LISTEN_PORT), ProxyHandler)
    server.allow_reuse_address = True
    print(f"🧷 SOCKS5 proxy {TARGET}:{TARGET_PORT} -> 0.0.0.0:{LISTEN_PORT}")
    server.serve_forever()