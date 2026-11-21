import http.server
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


SCRIPT = Path(__file__).resolve().parents[1] / "load" / "load.js"
K6 = os.environ.get("K6_BIN")


@unittest.skipUnless(K6, "укажите K6_BIN для интеграционных тестов k6")
class K6Test(unittest.TestCase):
    def test_full_profile_starts_with_one_and_ramps_to_four(self):
        result = subprocess.run(
            [K6, "inspect", "--execution-requirements", str(SCRIPT)],
            capture_output=True, text=True, check=True, timeout=10,
            env={k: v for k, v in os.environ.items() if k != "SMOKE"},
        )
        self.assertNotIn("unknown field", result.stderr)
        scenario = json.loads(result.stdout)["scenarios"]["default"]
        self.assertEqual(scenario["startVUs"], 1)
        self.assertEqual(scenario["stages"], [
            {"duration": "30s", "target": 4},
            {"duration": "3m0s", "target": 4},
        ])

    def run_load(self, url):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.json"
            result = subprocess.run(
                [K6, "run", "--quiet", "--summary-export", str(summary), str(SCRIPT)],
                env={**os.environ, "TARGET_URL": url, "SMOKE": "1"},
                capture_output=True, text=True, timeout=20,
            )
            self.assertTrue(summary.exists(), result.stderr)
            return result, json.loads(summary.read_text())["metrics"]

    def test_http_success_unique_queries_and_keepalive(self):
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                requests.append((self.path, self.client_address[1]))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result, metrics = self.run_load(f"http://127.0.0.1:{server.server_port}/")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreater(len(requests), 2)
            self.assertLess(len({port for _, port in requests}), len(requests) // 2)
            queries = [parse_qs(urlsplit(path).query) for path, _ in requests]
            self.assertEqual(len({q["cb"][0] for q in queries}), len(queries))
            self.assertGreater(len({q["p"][0] for q in queries}), 1)
            self.assertTrue(all(len(q["p"][0]) == 40 for q in queries))
            self.assertEqual(metrics["checks"]["passes"], len(requests))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_http_error_is_counted_and_fails_threshold(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(503)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result, metrics = self.run_load(f"http://127.0.0.1:{server.server_port}/")
            self.assertNotEqual(result.returncode, 0)
            self.assertGreater(metrics["http_errors"]["count"], 0)
            self.assertGreater(metrics["checks"]["fails"], 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_network_error_is_counted_and_fails_threshold(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        result, metrics = self.run_load(f"http://127.0.0.1:{port}/")
        self.assertNotEqual(result.returncode, 0)
        self.assertGreater(metrics["network_errors"]["count"], 0)
        self.assertGreater(metrics["checks"]["fails"], 0)
