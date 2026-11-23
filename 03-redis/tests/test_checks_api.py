import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from checks.client import HttpResponse, load_env_file  # noqa: E402


class LoadEnvFileTest(unittest.TestCase):
    def _write(self, content):
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_parses_key_value_lines(self):
        path = self._write("A=1\nB = two\n# comment\n\nC=x=y\n")
        values = load_env_file(path)
        self.assertEqual(values["A"], "1")
        self.assertEqual(values["B"], "two")
        self.assertEqual(values["C"], "x=y")
        self.assertNotIn("# comment", values)

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_env_file("/nonexistent/path/.env"), {})


class ClassifyDecisionTest(unittest.TestCase):
    def test_rejected_carries_reason(self):
        from checks.api import classify_decision

        response = HttpResponse(429, {"x-rate-limit-reason": "client"}, "")
        code, reason = classify_decision(response)
        self.assertEqual(code, 429)
        self.assertEqual(reason, "client")

    def test_header_lookup_is_case_insensitive(self):
        response = HttpResponse(429, {"X-Rate-Limit-Reason": "client"}, "")
        self.assertEqual(response.header("x-rate-limit-reason"), "client")
        response2 = HttpResponse(429, {"x-rate-limit-reason": "platform"}, "")
        self.assertEqual(response2.header("X-Rate-Limit-Reason"), "platform")

    def test_allowed_has_no_reason(self):
        from checks.api import classify_decision

        response = HttpResponse(200, {}, "[]")
        code, reason = classify_decision(response)
        self.assertEqual(code, 200)
        self.assertIsNone(reason)

    def test_parse_targets_maps_job_to_health(self):
        from checks.monitor import parse_targets

        payload = {"data": {"activeTargets": [
            {"labels": {"job": "app"}, "health": "up"},
            {"labels": {"job": "redis"}, "health": "down"},
        ]}}
        self.assertEqual(parse_targets(payload), {"app": "up", "redis": "down"})

    def test_query_result_count(self):
        from checks.monitor import query_result_count

        self.assertEqual(query_result_count({"data": {"result": [1, 2]}}), 2)
        self.assertEqual(query_result_count({"data": {"result": []}}), 0)


if __name__ == "__main__":
    unittest.main()
