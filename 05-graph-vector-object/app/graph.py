from typing import Dict, List, Optional

LABELS = {"table": ("Table", "fqn"), "dag": ("DAG", "name")}
DIRECTIONS = {"up", "down", "both"}
NODE_LIMIT = 2000
PATH_LIMIT = 2000


def parse_depth(value: Optional[str]) -> int:
    if value is None:
        return 3
    try:
        depth = int(value)
    except (TypeError, ValueError):
        raise ValueError("depth must be an integer between 1 and 10")
    if not 1 <= depth <= 10:
        raise ValueError("depth must be an integer between 1 and 10")
    return depth


def _kind_of(node) -> str:
    return "table" if "Table" in node.labels else "dag"


def _node_key(node) -> str:
    return node.get("fqn") if "Table" in node.labels else node.get("name")


def _node_payload(node) -> dict:
    kind = _kind_of(node)
    key = _node_key(node)
    return {
        "id": "{}:{}".format(kind, key),
        "kind": kind,
        "key": key,
        "label": node.get("name"),
        "props": dict(node.items()),
    }


def _edge_payload(relationship) -> dict:
    return {
        "source": "{}:{}".format(_kind_of(relationship.start_node), _node_key(relationship.start_node)),
        "target": "{}:{}".format(_kind_of(relationship.end_node), _node_key(relationship.end_node)),
        "mode": relationship.get("mode"),
    }


def get_node(driver, kind: str, key: str) -> Optional[dict]:
    if kind not in LABELS or not key:
        return None
    label, prop = LABELS[kind]
    query = "MATCH (n:{label} {{{prop}: $key}}) RETURN n LIMIT 1".format(
        label=label, prop=prop
    )
    with driver.session() as session:
        record = session.run(query, key=key).single()
    return _node_payload(record["n"]) if record else None


def search_nodes(driver, q: str, limit: int = 20) -> List[dict]:
    if not q.strip():
        return []
    limit = min(max(int(limit), 1), 20)
    query = (
        "CALL db.index.fulltext.queryNodes('nodeSearch', $q) "
        "YIELD node, score "
        "RETURN node, score ORDER BY score DESC LIMIT $limit"
    )
    substring_query = (
        "MATCH (n) "
        "WHERE (n:Table AND (toLower(n.fqn) CONTAINS $needle "
        "OR toLower(n.name) CONTAINS $needle)) "
        "OR (n:DAG AND toLower(n.name) CONTAINS $needle) "
        "RETURN n LIMIT $limit"
    )
    results = []
    seen = set()
    with driver.session() as session:
        for record in session.run(query, q=q, limit=limit):
            payload = dict(_node_payload(record["node"]), score=record["score"])
            results.append(payload)
            seen.add(payload["id"])
        if len(results) < limit:
            needle = q.strip().lower()
            records = session.run(
                substring_query, needle=needle, limit=limit - len(results)
            )
            for record in records:
                payload = dict(_node_payload(record["n"]), score=0.0)
                if payload["id"] not in seen:
                    results.append(payload)
                    seen.add(payload["id"])
    return results


def _path_query(kind: str, depth: int, direction: str) -> str:
    label, prop = LABELS[kind]
    if direction == "down":
        pattern = "(s:{label} {{{prop}: $key}})-[:LOADS*1..{depth}]->()".format(
            label=label, prop=prop, depth=depth
        )
    else:
        pattern = "(s:{label} {{{prop}: $key}})<-[:LOADS*1..{depth}]-()".format(
            label=label, prop=prop, depth=depth
        )
    return "MATCH p={pattern} RETURN p LIMIT {limit}".format(
        pattern=pattern, limit=PATH_LIMIT
    )


def _add_path(path, nodes: Dict[str, dict], edges: Dict[tuple, dict]) -> None:
    for node in path.nodes:
        payload = _node_payload(node)
        if payload["id"] not in nodes:
            nodes[payload["id"]] = payload
    for relationship in path.relationships:
        payload = _edge_payload(relationship)
        key = (payload["source"], payload["target"], payload["mode"])
        if key not in edges:
            edges[key] = payload


def lineage_subgraph(
    driver, kind: str, key: str, direction: str = "both", depth: int = 3
) -> Optional[dict]:
    if kind not in LABELS or direction not in DIRECTIONS:
        return None
    root = get_node(driver, kind, key)
    if root is None:
        return None

    nodes = {root["id"]: root}
    edges = {}
    truncated = False
    directions = ["down", "up"] if direction == "both" else [direction]
    with driver.session() as session:
        for item in directions:
            records = session.run(_path_query(kind, depth, item), key=key)
            path_count = 0
            for record in records:
                path_count += 1
                _add_path(record["p"], nodes, edges)
            if path_count >= PATH_LIMIT:
                truncated = True

    if len(nodes) > NODE_LIMIT:
        truncated = True
        kept_ids = list(nodes)[:NODE_LIMIT]
        kept = set(kept_ids)
        nodes = {node_id: nodes[node_id] for node_id in kept_ids}
        edges = {
            edge_key: edge
            for edge_key, edge in edges.items()
            if edge["source"] in kept and edge["target"] in kept
        }

    return {"nodes": list(nodes.values()), "edges": list(edges.values()), "truncated": truncated}


def parse_node_id(node_id: str):
    kind, separator, key = (node_id or "").partition(":")
    if not separator or kind not in LABELS or not key:
        return None
    return kind, key


def shortest_path(driver, from_id: str, to_id: str) -> Optional[dict]:
    parsed_from = parse_node_id(from_id)
    parsed_to = parse_node_id(to_id)
    if parsed_from is None or parsed_to is None:
        return None

    from_kind, from_key = parsed_from
    to_kind, to_key = parsed_to
    root = get_node(driver, from_kind, from_key)
    if root is None:
        return None
    if get_node(driver, to_kind, to_key) is None:
        return None
    if parsed_from == parsed_to:
        return {"nodes": [root], "edges": []}

    from_label, from_prop = LABELS[from_kind]
    to_label, to_prop = LABELS[to_kind]
    query = (
        "MATCH (a:{from_label} {{{from_prop}: $from_key}}), "
        "(b:{to_label} {{{to_prop}: $to_key}}) "
        "MATCH p=shortestPath((a)-[:LOADS*]-(b)) "
        "RETURN p LIMIT 1"
    ).format(
        from_label=from_label,
        from_prop=from_prop,
        to_label=to_label,
        to_prop=to_prop,
    )
    with driver.session() as session:
        record = session.run(
            query, from_key=from_key, to_key=to_key
        ).single()
    if record is None:
        return None
    path = record["p"]
    return {
        "nodes": [_node_payload(node) for node in path.nodes],
        "edges": [_edge_payload(relationship) for relationship in path.relationships],
    }