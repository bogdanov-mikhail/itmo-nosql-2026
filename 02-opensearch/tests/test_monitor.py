import unittest
from checks.monitor import nodes_with_data


class MonitorTest(unittest.TestCase):
    def test_reports_nodes_with_data(self):
        data = {"status": "success", "data": {"result": [
            {"metric": {"node": "os-hot"}, "value": [1, "42"]},
            {"metric": {"node": "os-warm"}, "value": [1, "13"]},
        ]}}
        self.assertEqual(nodes_with_data(data), {"os-hot", "os-warm"})

    def test_empty_result_is_not_success(self):
        self.assertEqual(nodes_with_data({"status": "success", "data": {"result": []}}), set())

    def test_error_is_not_success(self):
        self.assertEqual(nodes_with_data({"status": "error", "error": "metric missing"}), set())
