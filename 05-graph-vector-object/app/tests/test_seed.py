import json
from pathlib import Path

import pytest

import seed

CORE_PATH = Path(__file__).resolve().parent.parent / "core.json"


def core():
    return json.loads(CORE_PATH.read_text(encoding="utf-8"))


def count_nodes(driver):
    with driver.session() as session:
        return session.run("MATCH (n) RETURN count(n) AS n").single()["n"]


def test_find_cycle_detects_loop():
    edges = [
        {"from": "table:a", "to": "dag:b"},
        {"from": "dag:b", "to": "table:c"},
        {"from": "table:c", "to": "table:a"},
    ]
    cycle = seed.find_cycle(edges)
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"table:a", "dag:b", "table:c"}


def test_find_cycle_dag_ok():
    edges = [
        {"from": "table:a", "to": "dag:b"},
        {"from": "dag:b", "to": "table:c"},
        {"from": "table:c", "to": "dag:d"},
    ]
    assert seed.find_cycle(edges) is None


def test_find_cycle_self_loop():
    assert seed.find_cycle([{"from": "dag:a", "to": "dag:a"}]) == ["dag:a", "dag:a"]


@pytest.mark.integration
def test_load_core_counts(driver):
    data = core()
    stats = seed.load(data, driver)
    assert stats == {
        "tables": len(data["tables"]),
        "dags": len(data["dags"]),
        "edges": len(data["edges"]),
    }


@pytest.mark.integration
def test_load_idempotent(driver):
    data = core()
    seed.load(data, driver)
    before = count_nodes(driver)
    stats = seed.load(data, driver)
    assert count_nodes(driver) == before
    assert stats["edges"] == len(data["edges"])


@pytest.mark.integration
def test_schema_exists(driver):
    seed.ensure_schema(driver)
    with driver.session() as session:
        constraints = {row["name"] for row in session.run("SHOW CONSTRAINTS")}
        indexes = {row["name"] for row in session.run("SHOW INDEXES")}
    assert {"table_fqn", "dag_name"} <= constraints
    assert "nodeSearch" in indexes


@pytest.mark.integration
def test_cycle_rejected(driver):
    seed.load(core(), driver)
    before = count_nodes(driver)
    bad = {
        "tables": [
            {"fqn": "TestTmp.orders", "name": "TestTmp.orders", "system": "csv",
             "kind": "source", "description": "тестовый узел", "rows_approx": 1},
        ],
        "dags": [
            {"name": "TestTmp.job", "description": "тестовый процесс", "schedule": "-",
             "engine": "sql", "owner": "test", "steps": 1},
        ],
        "edges": [
            {"from": "table:TestTmp.orders", "to": "dag:TestTmp.job", "mode": "full"},
            {"from": "dag:TestTmp.job", "to": "table:TestTmp.orders", "mode": "full"},
        ],
    }
    with pytest.raises(seed.CycleError):
        seed.load(bad, driver)
    assert count_nodes(driver) == before