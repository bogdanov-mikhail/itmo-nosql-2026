"""Детерминированный генератор графа масштаба для нагрузочных прогонов.

Граф слоистый: source → staging → mart → report. Каждый DAG стоит на границе
двух соседних слоёв и связывает входы предыдущего слоя с выходами следующего,
поэтому циклы по LOADS невозможны по построению.
"""
from __future__ import annotations

import random

LAYERS = ["source", "staging", "mart", "report"]

DEFAULT_TABLES = 5000
DEFAULT_DAGS = 1500
DEFAULT_SEED = 42


def _layer_of(index, total):
    """Раскладывает таблицы по слоям примерно 20/30/30/20."""
    share = (index + 0.5) / total
    if share < 0.2:
        return 0
    if share < 0.5:
        return 1
    if share < 0.8:
        return 2
    return 3


def _boundary(rnd, index):
    """Граница слоёв для DAG: первые три фиксированы, дальше — по весам."""
    if index < 3:
        return index
    roll = rnd.random()
    if roll < 0.5:
        return 0
    if roll < 0.8:
        return 1
    return 2


def generate_scale(tables: int = DEFAULT_TABLES, dags: int = DEFAULT_DAGS,
                   seed: int = DEFAULT_SEED) -> dict:
    rnd = random.Random(seed)

    table_rows = []
    by_layer = [[] for _ in LAYERS]
    for i in range(tables):
        layer = _layer_of(i, tables)
        fqn = f"gen_s{seed}.t{i:05d}"
        row = {
            "fqn": fqn,
            "name": fqn,
            "system": "generated",
            "kind": LAYERS[layer],
            "description": f"Синтетическая таблица слоя «{LAYERS[layer]}» для нагрузки.",
            "rows_approx": 1000 + i * 7,
        }
        table_rows.append(row)
        by_layer[layer].append(fqn)

    dag_rows = []
    boundaries = []
    for j in range(dags):
        boundary = _boundary(rnd, j)
        boundaries.append(boundary)
        name = f"gen_s{seed}_d{j:04d}"
        dag_rows.append({
            "name": name,
            "description": (
                f"Синтетический конвейер {LAYERS[boundary]} → {LAYERS[boundary + 1]}."
            ),
            "schedule": "0 3 * * *",
            "engine": "sql" if j % 2 else "python",
            "owner": "load-generator",
            "steps": rnd.randint(2, 12),
        })

    edges = {}
    used_inputs = set()
    used_outputs = set()

    for j, boundary in enumerate(boundaries):
        sources = by_layer[boundary]
        targets = by_layer[boundary + 1]
        if not sources or not targets:
            continue
        dag_id = f"dag:{dag_rows[j]['name']}"
        for _ in range(rnd.randint(1, 4)):
            fqn = rnd.choice(sources)
            used_inputs.add(fqn)
            edges[(f"table:{fqn}", dag_id)] = {
                "from": f"table:{fqn}", "to": dag_id,
                "mode": "incremental" if rnd.random() < 0.5 else "full",
            }
        for _ in range(rnd.randint(1, 4)):
            fqn = rnd.choice(targets)
            used_outputs.add(fqn)
            edges[(dag_id, f"table:{fqn}")] = {
                "from": dag_id, "to": f"table:{fqn}",
                "mode": "incremental" if rnd.random() < 0.5 else "full",
            }

    # Каждая таблица должна попасть хотя бы в один конвейер.
    dag_by_boundary = {}
    for j, boundary in enumerate(boundaries):
        dag_by_boundary.setdefault(boundary, []).append(dag_rows[j]["name"])
    for i, table in enumerate(table_rows):
        fqn = table["fqn"]
        layer = _layer_of(i, tables)
        if layer == 0:
            if fqn in used_inputs or not dag_by_boundary.get(0):
                continue
            dag_id = f"dag:{dag_by_boundary[0][i % len(dag_by_boundary[0])]}"
            edges[(f"table:{fqn}", dag_id)] = {
                "from": f"table:{fqn}", "to": dag_id, "mode": "full",
            }
        else:
            if fqn in used_outputs or not dag_by_boundary.get(layer - 1):
                continue
            dags_here = dag_by_boundary[layer - 1]
            dag_id = f"dag:{dags_here[i % len(dags_here)]}"
            edges[(dag_id, f"table:{fqn}")] = {
                "from": dag_id, "to": f"table:{fqn}", "mode": "full",
            }

    return {"tables": table_rows, "dags": dag_rows, "edges": list(edges.values())}