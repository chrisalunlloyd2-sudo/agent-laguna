#!/usr/bin/env python3
"""Deterministic integration test for hexflow_server.py (stdlib only).

Covers the read-only surface the SHUTTLE @VERIFY step depends on:
  GET /health  -> 200 {"status": "ok"}
  GET /status  -> 200 dict (hexflow_contract.status())
  GET /inbox   -> 200 list (hexflow_contract.pending_inbox_actions())
  GET /nope    -> 404 {"error": "not found"}

No network, no third-party deps: the server binds 127.0.0.1:0 (ephemeral)
inside a daemon thread and is shut down in tearDown.
"""
import http.client
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import HTTPServer  # noqa: E402

import hexflow_server  # noqa: E402


class HexflowServerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), hexflow_server.HexflowHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read().decode("utf-8"))
        finally:
            conn.close()

    def test_health(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_status(self):
        status, body = self._get("/status")
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertGreater(len(body), 0)

    def test_inbox(self):
        status, body = self._get("/inbox")
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_unknown_route_404(self):
        status, body = self._get("/definitely-not-a-route")
        self.assertEqual(status, 404)
        self.assertEqual(body.get("error"), "not found")


if __name__ == "__main__":
    unittest.main()
