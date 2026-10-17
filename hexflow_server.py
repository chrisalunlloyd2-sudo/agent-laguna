#!/usr/bin/env python3
"""
hexflow_server.py — HTTP server wrapper for the ARIA Hex-flow contract processor.

Provides a lightweight stdlib-only HTTP server that exposes hexflow operations:
  GET  /health   — health check
  GET  /status   — current shuttle status
  GET  /inbox    — pending inbox actions
  POST /cycle    — run one hexflow cycle

Usage:
  python3 hexflow_server.py [--port PORT] [--host HOST]
"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Ensure sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))
import hexflow_contract  # noqa: E402


class HexflowHandler(BaseHTTPRequestHandler):
    """HTTP request handler for hexflow operations."""

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok"})
        elif self.path == "/status":
            self._send_json(hexflow_contract.status())
        elif self.path == "/inbox":
            self._send_json(hexflow_contract.pending_inbox_actions())
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        if self.path == "/cycle":
            result = hexflow_contract.run_hexflow_cycle()
            self._send_json(result)
        else:
            self._send_json({"error": "not found"}, status=404)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def serve(host="127.0.0.1", port=8765):
    """Start the hexflow HTTP server."""
    server = HTTPServer((host, port), HexflowHandler)
    print(f"hexflow_server listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down hexflow_server...")
        server.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ARIA Hex-flow server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
