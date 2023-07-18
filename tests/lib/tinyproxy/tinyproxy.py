#!/usr/bin/python3

# Tiny HTTP Proxy. Based on the work of SUZUKI Hisao.
#
# Ported to py3 and modified to remove the bits we don't need
# and modernized.

import os
import http.server
import select
import socket
import socketserver
import sys
import urllib.parse


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    server_version = "testsproxy/1.0"

    def log_request(self, m=""):
        super().log_request(m)
        sys.stdout.flush()
        sys.stderr.flush()

    def handle(self):
        (ip, port) = self.client_address
        super().handle()

    def _connect_to(self, netloc, soc):
        i = netloc.find(":")
        host_port = (netloc[:i], int(netloc[i + 1 :])) if i >= 0 else (netloc, 80)
        try:
            soc.connect(host_port)
        except socket.error as arg:
            try:
                msg = arg[1]
            except:
                msg = arg
            self.send_error(404, msg)
            return False
        return True

    def do_CONNECT(self):
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(self.path, soc):
                self.log_request(200)
                s = self.protocol_version + " 200 Connection established\r\n"
                self.wfile.write(s.encode())
                s = f"Proxy-agent: {self.version_string()}\r\n"
                self.wfile.write(s.encode())
                self.wfile.write("\r\n".encode())
                self._read_write(soc, 300)
        finally:
            soc.close()
            self.connection.close()

    def do_GET(self):
        (scm, netloc, path, params, query, fragment) = urllib.parse.urlparse(
            self.path, "http"
        )
        if scm != "http" or fragment or not netloc:
            s = f"bad url {self.path}"
            self.send_error(400, s.encode())
            return
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(netloc, soc):
                self.log_request()
                s = f'{self.command} {urllib.parse.urlunparse(("", "", path, params, query, ""))} {self.request_version}\r\n'
                soc.send(s.encode())
                self.headers["Connection"] = "close"
                del self.headers["Proxy-Connection"]
                for key, val in self.headers.items():
                    s = f"{key}: {val}\r\n"
                    soc.send(s.encode())
                soc.send("\r\n".encode())
                self._read_write(soc)
        finally:
            soc.close()
            self.connection.close()

    def _read_write(self, soc, max_idling=20):
        iw = [self.connection, soc]
        ow = []
        count = 0
        while True:
            count += 1
            (ins, _, exs) = select.select(iw, ow, iw, 3)
            if exs:
                break
            if ins:
                for i in ins:
                    out = self.connection if i is soc else soc
                    if data := i.recv(8192):
                        out.send(data)
                        count = 0
            if count == max_idling:
                break

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET


def maybe_sd_notify(s: str) -> None:
    addr = os.getenv("NOTIFY_SOCKET")
    if not addr:
        return
    soc = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    soc.connect(addr)
    soc.sendall(s.encode())


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def __init__(self, *args):
        super().__init__(*args)
        maybe_sd_notify("READY=1")


if __name__ == "__main__":
    port = 3128
    print(f"starting tinyproxy on port {port}")
    http.server.test(ProxyHandler, ThreadingHTTPServer, port=port)
