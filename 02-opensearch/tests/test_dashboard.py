import json
import unittest
from pathlib import Path


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "grafana/dashboards/coffee-os.json"
        cls.panels = {panel["title"]: panel for panel in json.loads(path.read_text())["panels"]}

    def test_cluster_status_mapping(self):
        panel = self.panels["Статус кластера (0 green / 1 yellow / 2 red)"]
        values = panel["fieldConfig"]["defaults"]["mappings"][0]["options"]
        self.assertEqual([values[str(i)]["text"] for i in range(3)], ["GREEN", "YELLOW", "RED"])

    def test_promql_grouping_and_gc_units(self):
        queries = {
            "GC: время сборок, с/мин": "60 * sum by (node, gc) (rate(opensearch_jvm_gc_collection_time_seconds[1m]))",
            "Rate индексации (приём логов), ops/с": "sum by (node) (rate(opensearch_indices_indexing_index_count[1m]))",
            "Поиск, запросов/с": "sum by (node) (rate(opensearch_indices_search_query_count[1m]))",
        }
        for title, expected in queries.items():
            with self.subTest(panel=title):
                self.assertEqual(self.panels[title]["targets"][0]["expr"], expected)

    def test_node_counts_have_one_series_per_cluster_and_clear_labels(self):
        targets = self.panels["Узлы (всего / с данными)"]["targets"]
        self.assertEqual(
            [(target["expr"], target.get("legendFormat")) for target in targets],
            [
                ("max by (cluster) (opensearch_cluster_nodes_number)", "Всего узлов"),
                ("max by (cluster) (opensearch_cluster_datanodes_number)", "С данными"),
            ],
        )
