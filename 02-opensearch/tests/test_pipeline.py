import unittest
from checks.pipeline import missing_requests


class PipelineTest(unittest.TestCase):
    def test_detects_missing_even_with_duplicates(self):
        self.assertEqual(missing_requests({"a", "b"}, ["a", "a"]), {"b"})

    def test_all_requests_present(self):
        self.assertEqual(missing_requests({"a", "b"}, ["b", "a"]), set())
