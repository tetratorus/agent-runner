#!/usr/bin/env python3
"""Host-side awal proxy.

Container `awal` shim sends `{"argv": [...]}` over TCP; this process runs the
real `awal` CLI on the host and returns `{"stdout","stderr","rc"}`. The host's
awal server stays authenticated across container runs because it's never killed.

Run on the host (keep it alive for the whole benchmark):

    python3 benchmark/wallets/awal/host-awal-proxy.py

Listens on 0.0.0.0:7788. Requires `awal` on PATH and an authenticated session.
"""
import json
import socketserver
import subprocess
import sys

PORT = 7788
TIMEOUT_S = 180


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline()
        if not line:
            return
        try:
            req = json.loads(line.decode())
            argv = list(req.get("argv", []))
        except Exception as e:
            self._reply({"stdout": "", "stderr": f"bad request: {e}\n", "rc": 2})
            return

        try:
            result = subprocess.run(
                ["awal", *argv],
                capture_output=True, text=True, timeout=TIMEOUT_S,
            )
            self._reply({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "rc": result.returncode,
            })
        except subprocess.TimeoutExpired:
            self._reply({"stdout": "", "stderr": f"awal timed out after {TIMEOUT_S}s\n", "rc": 124})
        except FileNotFoundError:
            self._reply({"stdout": "", "stderr": "awal not on host PATH\n", "rc": 127})
        except Exception as e:
            self._reply({"stdout": "", "stderr": f"proxy error: {e}\n", "rc": 1})

    def _reply(self, payload):
        self.wfile.write((json.dumps(payload) + "\n").encode())


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedServer(("0.0.0.0", PORT), Handler) as srv:
        print(f"awal-host-proxy listening on 0.0.0.0:{PORT}", file=sys.stderr)
        srv.serve_forever()
