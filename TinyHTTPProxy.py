#!/usr/bin/env python

"""Tiny HTTP Proxy

This module implements GET, HEAD, POST, PUT, DELETE and CONNECT methods
on BaseHTTPServer (or server.http), and behaves as an HTTP proxy.
"""

from __future__ import print_function

__version__ = "1.1.1"

import select, socket, sys

try:
    import http.server as hserv
    from socketserver import ThreadingMixIn
    import urllib.parse as urlparse
    print_word = lambda wd: print(wd, end="\t", flush=True)
    _ = lambda s: s.encode('utf-8')
except ImportError:
    import BaseHTTPServer as hserv
    from SocketServer import ThreadingMixIn
    import urlparse
    print_word = lambda s: (print(s, end="\t"), sys.stdout.flush())
    _ = lambda s: s

class ProxyHandler (hserv.BaseHTTPRequestHandler):
    __base = hserv.BaseHTTPRequestHandler
    __base_handle = __base.handle

    server_version = "TinyHTTPProxy/" + __version__
    rbufsize = 0                        # self.rfile Be unbuffered

    def handle(self):
        (ip, port) =  self.client_address
        if hasattr(self, 'allowed_clients') and ip not in self.allowed_clients:
            self.raw_requestline = self.rfile.readline()
            if self.parse_request(): self.send_error(403)
        else:
            self.__base_handle()

    def _connect_to(self, netloc, soc):
        i = netloc.find(':')
        if i >= 0:
            host_port = netloc[:i], int(netloc[i+1:])
        else:
            host_port = netloc, 80
        print("\t" "connect to %s:%d" % host_port)
        try: soc.connect(host_port)
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
                self.wfile.write(_(self.protocol_version +
                                   " 200 Connection established\r\n"))
                self.wfile.write(_("Proxy-agent: %s\r\n" %
                                   self.version_string()))
                self.wfile.write(b"\r\n")
                self._read_write(soc, 300)
        finally:
            print_word("bye")
            soc.close()
            self.connection.close()

    def do_GET(self):
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(
            self.path, 'http')
        if scm != 'http' or fragment or not netloc:
            self.send_error(400, "bad url %s" % self.path)
            return
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self._connect_to(netloc, soc):
                self.log_request()
                soc.send(_("%s %s %s\r\n" % (
                            self.command,
                            urlparse.urlunparse(('', '', path, params, query,
                                                 '')),
                            self.request_version)))
                self.headers['Connection'] = 'close'
                del self.headers['Proxy-Connection']
                for key_val in self.headers.items():
                    soc.send(_("%s: %s\r\n" % key_val))
                soc.send(b"\r\n")
                self._read_write(soc)
        finally:
            print_word("bye")
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
                    if i is soc:
                        out = self.connection
                    else:
                        out = soc
                    data = i.recv(8192)
                    if data:
                        out.send(data)
                        count = 0
            else:
                print_word(count)
            if count == max_idling:
                break

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT  = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET

class ThreadingHTTPServer (ThreadingMixIn, hserv.HTTPServer):
    pass

def main(argv):
    if argv[1:] and argv[1] in ('-h', '--help'):
        print(argv[0], "[port [allowed_client_name ...]]")
    else:
        server_address = ('', int(argv[1]) if argv[1:] else 8000)
        if argv[2:]:
            allowed = []
            for name in argv[2:]:
                client = socket.gethostbyname(name)
                allowed.append(client)
                print("Accept: %s (%s)" % (client, name))
            ProxyHandler.allowed_clients = allowed
        else:
            print("Any clients will be served...")
        httpd = ThreadingHTTPServer(server_address, ProxyHandler)
        (host, port) = httpd.socket.getsockname()
        print("Serving", ProxyHandler.protocol_version,
              "on", host, "port", port, "...")
        httpd.serve_forever()

if __name__ == '__main__':
    main(sys.argv)
