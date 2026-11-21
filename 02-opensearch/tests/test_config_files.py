import json
import unittest
from pathlib import Path


class ConfigTest(unittest.TestCase):
    def test_ism_policy_and_index_template(self):
        root = Path(__file__).resolve().parents[1] / "setup" / "config"
        policy = json.loads((root / "lifecycle.json").read_text())
        template = json.loads((root / "log-template.json").read_text())
        self.assertEqual(policy["policy"]["states"][0]["actions"][0]["rollover"],
                         {"min_size": "1mb", "min_index_age": "1m"})
        self.assertEqual(template["index_patterns"], ["logs"])
        self.assertEqual(template["template"]["settings"]["number_of_replicas"], 0)
