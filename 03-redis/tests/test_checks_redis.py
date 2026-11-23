import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "checks"))

from checks.redis_state import parse_pttl, parse_scan_output  # noqa: E402


class ParseScanOutputTest(unittest.TestCase):
    def test_filters_bucket_keys_only(self):
        raw = "ratelimit:client:abc\nsome-other-key\nratelimit:client:def\n"
        self.assertEqual(parse_scan_output(raw), ["ratelimit:client:abc", "ratelimit:client:def"])

    def test_ignores_blank_lines(self):
        self.assertEqual(parse_scan_output("\n \nratelimit:client:x\n\n"), ["ratelimit:client:x"])

    def test_empty_output(self):
        self.assertEqual(parse_scan_output(""), [])


class ParsePttlTest(unittest.TestCase):
    def test_positive_ttl(self):
        self.assertEqual(parse_pttl("59123\n"), 59123)

    def test_no_expiry_minus_one(self):
        self.assertEqual(parse_pttl("-1"), -1)

    def test_missing_key_minus_two(self):
        self.assertEqual(parse_pttl("-2"), -2)

    def test_garbage_is_none(self):
        self.assertIsNone(parse_pttl("WRONGTYPE ..."))


if __name__ == "__main__":
    unittest.main()
