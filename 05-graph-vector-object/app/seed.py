"""Загрузка каталога data lineage в Neo4j.

Схема: узлы Table и DAG, связь LOADS (данные загружаются в).
Загрузка идемпотентна (MERGE), цикл по LOADS отвергается целиком.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from neo4j import GraphDatabase

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT table_fqn IF NOT EXISTS FOR (t:Table) REQUIRE t.fqn IS UNIQUE",
    "CREATE CONSTRAINT dag_name IF NOT EXISTS FOR (d:DAG) REQUIRE d.name IS UNIQUE",
    "CREATE FULLTEXT INDEX nodeSearch IF NOT EXISTS "
    "FOR (n:Table|DAG) ON EACH [n.name, n.description]",
]

LABELS = {"table": ("Table", "fqn"), "dag": ("DAG", "name")}

BATCH_SIZE = 500


class CycleError(Exception):
    """В данных обнаружен цикл по LOADS; загрузка отменена."""

    def __init__(self, cycle):
        self.cycle = cycle
        super().__init__("cycle detected: " + " -> ".join(cycle))


def find_cycle(edges):
    """Возвращает путь цикла по рёбрам {"from","to"} или None, если граф ацикличен."""
    graph = {}
    for edge in edges:
        graph.setdefault(edge["from"], []).append(edge["to"])
        graph.setdefault(edge["to"], [])

    white, gray, black = 0, 1, 2
    color = {node: white for node in graph}
    stack = []

    def visit(node):
        color[node] = gray
        stack.append(node)
        for nxt in graph[node]:
            if color[nxt] == gray:
                return stack[stack.index(nxt):] + [nxt]
            if color[nxt] == white:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return None

    for node in graph:
        if color[node] == white:
            found = visit(node)
            if found:
                return found
    return None


def connect():
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_schema(driver):
    """Создаёт ограничения и полнотекстовый индекс, если их ещё нет."""
    with driver.session() as session:
        for statement in SCHEMA_STATEMENTS:
            session.run(statement).consume()


def merge_data(parts):
    merged = {"tables": [], "dags": [], "edges": []}
    for part in parts:
        for name in merged:
            merged[name].extend(part.get(name, []))
    return merged


def _split_id(node_id):
    kind, key = node_id.split(":", 1)
    if kind not in LABELS:
        raise ValueError(f"unknown node kind in id: {node_id}")
    return kind, key


def _batches(rows):
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start:start + BATCH_SIZE]


def _existing_ids(tx):
    result = tx.run(
        "MATCH (n) RETURN labels(n)[0] AS label, coalesce(n.fqn, n.name) AS key"
    )
    ids = set()
    for row in result:
        kind = "table" if row["label"] == "Table" else "dag"
        ids.add(f"{kind}:{row['key']}")
    return ids


def _existing_edges(tx):
    result = tx.run(
        "MATCH (a)-[:LOADS]->(b) "
        "RETURN labels(a)[0] AS a_label, coalesce(a.fqn, a.name) AS a_key, "
        "labels(b)[0] AS b_label, coalesce(b.fqn, b.name) AS b_key"
    )
    edges = []
    for row in result:
        a_kind = "table" if row["a_label"] == "Table" else "dag"
        b_kind = "table" if row["b_label"] == "Table" else "dag"
        edges.append({
            "from": f"{a_kind}:{row['a_key']}",
            "to": f"{b_kind}:{row['b_key']}",
        })
    return edges


def _write(tx, data):
    new_edges = [{"from": e["from"], "to": e["to"]} for e in data["edges"]]

    data_ids = {f"table:{t['fqn']}" for t in data["tables"]}
    data_ids |= {f"dag:{d['name']}" for d in data["dags"]}
    known = data_ids | _existing_ids(tx)
    for edge in new_edges:
        for endpoint in (edge["from"], edge["to"]):
            if endpoint not in known:
                raise ValueError(f"edge references unknown node: {endpoint}")

    cycle = find_cycle(_existing_edges(tx) + new_edges)
    if cycle:
        raise CycleError(cycle)

    for batch in _batches(data["tables"]):
        tx.run(
            "UNWIND $rows AS row MERGE (n:Table {fqn: row.fqn}) SET n += row",
            rows=batch,
        ).consume()

    for batch in _batches(data["dags"]):
        tx.run(
            "UNWIND $rows AS row MERGE (n:DAG {name: row.name}) SET n += row",
            rows=batch,
        ).consume()

    groups = {}
    for edge in data["edges"]:
        from_kind, from_key = _split_id(edge["from"])
        to_kind, to_key = _split_id(edge["to"])
        groups.setdefault((from_kind, to_kind), []).append({
            "from_key": from_key,
            "to_key": to_key,
            "mode": edge.get("mode", "full"),
        })

    for (from_kind, to_kind), rows in groups.items():
        from_label, from_prop = LABELS[from_kind]
        to_label, to_prop = LABELS[to_kind]
        query = (
            f"UNWIND $rows AS row "
            f"MERGE (a:{from_label} {{{from_prop}: row.from_key}}) "
            f"MERGE (b:{to_label} {{{to_prop}: row.to_key}}) "
            f"MERGE (a)-[rel:LOADS]->(b) SET rel.mode = row.mode"
        )
        for batch in _batches(rows):
            tx.run(query, rows=batch).consume()


def load(data, driver):
    """Загружает узлы и связи одной транзакцией; возвращает счётчики входных данных."""
    with driver.session() as session:
        session.execute_write(_write, data)
    return {
        "tables": len(data["tables"]),
        "dags": len(data["dags"]),
        "edges": len(data["edges"]),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Загрузка каталога lineage в Neo4j")
    parser.add_argument("--scale", action="store_true", help="добавить сгенерированный граф")
    parser.add_argument("--tables", type=int, default=5000, help="таблиц в масштабе")
    parser.add_argument("--dags", type=int, default=1500, help="DAG в масштабе")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    core = json.loads(Path(__file__).with_name("core.json").read_text(encoding="utf-8"))
    data = core
    if args.scale:
        from generate import generate_scale

        data = merge_data([core, generate_scale(tables=args.tables, dags=args.dags)])

    driver = connect()
    try:
        ensure_schema(driver)
        stats = load(data, driver)
    finally:
        driver.close()
    print(
        "loaded: tables={tables} dags={dags} edges={edges}".format(**stats)
    )


if __name__ == "__main__":
    main()