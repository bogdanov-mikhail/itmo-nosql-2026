import http.server
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


HELPER = Path(__file__).resolve().parents[1] / "setup" / "ism-policy.sh"


class PolicyUpdateTest(unittest.TestCase):
    def exercise(self, status, body):
        calls = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(("GET", self.path))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(body.encode())

            def do_PUT(self):
                calls.append(("PUT", self.path))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            script = '''
set -eu
api() { curl -sf "$@"; }
policy_get() { curl -sS -w '\\n%{http_code}' "$@"; }
. "$HELPER"
update_ism_policy
'''
            with tempfile.NamedTemporaryFile() as policy:
                result = subprocess.run(
                    ["sh", "-c", script],
                    env={**os.environ, "HELPER": str(HELPER), "POLICY_FILE": policy.name,
                         "OS": f"http://127.0.0.1:{server.server_port}"},
                    capture_output=True, text=True, timeout=10,
                )
            return result, calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_existing_policy_versions(self):
        for body in ('{"_seq_no": 7, "_primary_term": 2}',
                     '{ "_primary_term" : 2, "nested": {"x": 1}, "_seq_no" : 7 }'):
            with self.subTest(body=body):
                result, calls = self.exercise(200, body)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(calls, [
                    ("GET", "/_plugins/_ism/policies/logs-lifecycle"),
                    ("PUT", "/_plugins/_ism/policies/logs-lifecycle?if_seq_no=7&if_primary_term=2"),
                ])

    def test_only_404_creates(self):
        result, calls = self.exercise(404, '{}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[-1], ("PUT", "/_plugins/_ism/policies/logs-lifecycle"))

    def test_bad_responses_never_write(self):
        for status, body in [(401, '{}'), (500, '{}'), (201, '{}'), (200, 'no json'),
                             (200, '{}'), (200, '{"_seq_no": 1.5, "_primary_term": 1}'),
                             (200, '{"_seq_no": "1", "_primary_term": 1}'),
                             (200, '{"_seq_no": -1, "_primary_term": 1}'),
                             (200, '{"_seq_no": 1, "_primary_term": 1} {}')]:
            with self.subTest(status=status, body=body):
                result, calls = self.exercise(status, body)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(calls), 1)
