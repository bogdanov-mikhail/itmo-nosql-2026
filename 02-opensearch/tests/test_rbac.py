import unittest

from checks.rbac import bulk_succeeded, deletion_denied


class BulkTest(unittest.TestCase):
    def test_delete_simulation_must_explicitly_deny(self):
        self.assertTrue(deletion_denied({"accessAllowed": False, "missingPrivileges": ["indices:admin/data_stream/delete"]}))
        self.assertFalse(deletion_denied({"accessAllowed": True, "missingPrivileges": []}))
        self.assertFalse(deletion_denied({}))

    def test_accepts_created_document(self):
        self.assertTrue(bulk_succeeded({"errors": False, "items": [{"create": {"status": 201}}]}))

    def test_rejects_embedded_error(self):
        self.assertFalse(bulk_succeeded({"errors": True, "items": [{"create": {"status": 403}}]}))

    def test_rejects_missing_items(self):
        self.assertFalse(bulk_succeeded({"errors": False, "items": []}))
