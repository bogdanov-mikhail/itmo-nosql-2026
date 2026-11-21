import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from checks.client import Client


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(403 if self.path == "/denied" else 200)
        self.end_headers()
        self.wfile.write(b"not json" if self.path == "/invalid" else b'{"ok":true}')

    def log_message(self, *args):
        pass


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = Client(f"http://127.0.0.1:{cls.server.server_port}")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_json_response(self):
        self.assertEqual(self.client.json("/ok"), {"ok": True})

    def test_http_error_is_not_success(self):
        with self.assertRaises(Exception):
            self.client.json("/denied")

    def test_invalid_json_is_not_success(self):
        with self.assertRaises(json.JSONDecodeError):
            self.client.json("/invalid")


if __name__ == "__main__":
    unittest.main()
