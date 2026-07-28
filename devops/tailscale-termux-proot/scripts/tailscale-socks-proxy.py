#!/usr/bin/env python3
"""TCP proxy: listen on PORT -> forward via SOCKS5 to TARGET:PORT

Usage:
    python3 tailscale-socks-proxy.py 9119 100.78.85.64 9119
    
This creates a TCP bridge on 0.0.0.0:9119 that forwards all connections
to 100.78.85.64:9119 through the SOCKS5 proxy at 127.0.0.1:1080.

Useful when tailscaled runs in --tun=userspace-networking mode and
the host OS has no kernel-level route to tailnet IPs (100.x.x.x).
"""
import socketserver, socket, struct, threading, sys

SOCKS5_HOST = "127.0.0.1"
SOCKS5_PORT = 1080
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9119
TARGET = sys.argv[2] if len(sys.argv) > 2 else "100.78.85.64"
TARGET_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else LISTEN_PORT
BUF = 65536

def recvall(s, n):
    d = b""
    while len(d) < n:
        c = s.recv(n - len(d))
        if not c: raise ConnectionError("closed")
        d += c
    return d

def socks5_connect(dst, prt):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15)
    s.connect((SOCKS5_HOST, SOCKS5_PORT))
    s.sendall(b"\x05\x01\x00")
    recvall(s, 2)  # ver, method
    s.sendall(b"\x05\x01\x00\x01" + socket.inet_aton(dst) + struct.pack(">H", prt))
    r = recvall(s, 10)
    assert r[1] == 0, f"SOCKS5 connect failed, status={r[1]}"
    s.settimeout(None)
    return s

def pipe(a, b):
    try:
        while True:
            d = a.recv(BUF)
            if not d: break
            b.sendall(d)
    except: pass
    finally:
        for x in (a, b):
            try: x.close()
            except: pass

class ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        local = self.request
        try:
            remote = socks5_connect(TARGET, TARGET_PORT)
        except Exception as e:
            local.close()
            return
        t1 = threading.Thread(target=pipe, args=(local, remote), daemon=True)
        t2 = threading.Thread(target=pipe, args=(remote, local), daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()

if __name__ == "__main__":
    server = socketserver.ThreadingTCPServer(
        ("0.0.0.0", LISTEN_PORT), ProxyHandler
    )
    server.allow_reuse_address = True
    print(f"🧷 SOCKS5 proxy {TARGET}:{TARGET_PORT} -> 0.0.0.0:{LISTEN_PORT}")
    server.serve_forever()