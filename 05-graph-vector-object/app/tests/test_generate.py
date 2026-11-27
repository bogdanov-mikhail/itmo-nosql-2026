import json
from pathlib import Path

import generate
import seed

CORE = json.loads((Path(__file__).resolve().parent.parent / "core.json").read_text(encoding="utf-8"))


def test_deterministic():
    first = generate.generate_scale(tables=60, dags=12, seed=42)
    second = generate.generate_scale(tables=60, dags=12, seed=42)
    assert first == second


def test_counts():
    data = generate.generate_scale(tables=40, dags=8, seed=7)
    assert len(data["tables"]) == 40
    assert len(data["dags"]) == 8


def test_acyclic():
    data = generate.generate_scale(tables=120, dags=30, seed=42)
    assert seed.find_cycle(data["edges"]) is None


def test_keys_unique():
    data = generate.generate_scale(tables=80, dags=20, seed=42)
    fqns = [table["fqn"] for table in data["tables"]]
    names = [dag["name"] for dag in data["dags"]]
    assert len(fqns) == len(set(fqns))
    assert len(names) == len(set(names))
    assert not set(fqns) & {table["fqn"] for table in CORE["tables"]}
    assert not set(names) & {dag["name"] for dag in CORE["dags"]}


def test_edges_reference_existing():
    data = generate.generate_scale(tables=100, dags=25, seed=42)
    known = {f"table:{t['fqn']}" for t in data["tables"]}
    known |= {f"dag:{d['name']}" for d in data["dags"]}
    assert data["edges"]
    for edge in data["edges"]:
        assert edge["from"] in known
        assert edge["to"] in known