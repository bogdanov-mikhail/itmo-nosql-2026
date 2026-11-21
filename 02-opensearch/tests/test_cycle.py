import unittest
from checks.cycle import index_deleted, is_warm_readonly
from urllib.error import HTTPError


class CycleTest(unittest.TestCase):
    def test_only_http_404_proves_deletion(self):
        class FakeClient:
            def request(self, path, method):
                raise HTTPError(path, 403, "forbidden", {}, None)
        with self.assertRaises(HTTPError):
            index_deleted(FakeClient(), ".ds-logs-000001")

    def test_warm_requires_write_block(self):
        self.assertFalse(is_warm_readonly(
            [{"prirep": "p", "state": "STARTED", "node": "os-warm"}],
            {".ds-logs-000001": {"settings": {"index.blocks.write": "false"}}},
            ".ds-logs-000001"))

    def test_warm_and_readonly(self):
        self.assertTrue(is_warm_readonly(
            [{"prirep": "p", "state": "STARTED", "node": "os-warm"}],
            {".ds-logs-000001": {"settings": {"index.blocks.write": "true"}}},
            ".ds-logs-000001"))
