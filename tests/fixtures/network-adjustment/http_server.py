"""A test-owned server reports raw identity; it contains no adjustment policy."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys


marker = (sys.argv[2] + '\n').encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(marker)


server = HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler)
ticks = Path('/proc/self/stat').read_text().rpartition(')')[2].split()[19]
print(json.dumps(dict(pid=os.getpid(), port=server.server_port, start_ticks=ticks)), flush=True)
server.serve_forever()
