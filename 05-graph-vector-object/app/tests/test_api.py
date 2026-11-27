import neo4j
import pytest
from fastapi.testclient import TestClient

from main import app, get_driver

pytestmark = pytest.mark.integration

CORE_TABLE = "mongo.spa.appointments"
CORE_REPORT = "report.revenue_dashboard"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def cleanup_test_nodes(driver):
    with driver.session() as session:
        session.run("MATCH (n:TestTmp) DETACH DELETE n")


def test_lineage_down_from_table(client):
    response = client.get(
        f"/api/lineage/table/{CORE_TABLE}", params={"direction": "down", "depth": 3}
    )
    assert response.status_code == 200
    body = response.json()
    ids = {node["id"] for node in body["nodes"]}
    assert f"table:{CORE_TABLE}" in ids
    assert any(node_id.startswith("table:stg.") for node_id in ids)
    assert any(node_id.startswith("dag:") for node_id in ids)
    assert body["truncated"] is False
    for edge in body["edges"]:
        assert edge["mode"] in {"full", "incremental"}
        assert edge["source"] in ids and edge["target"] in ids
    root = next(node for node in body["nodes"] if node["id"] == f"table:{CORE_TABLE}")
    assert root["kind"] == "table"
    assert root["props"]["fqn"] == CORE_TABLE
    assert any(
        edge["source"] == f"table:{CORE_TABLE}" and edge["target"].startswith("dag:")
        for edge in body["edges"]
    )


def test_lineage_up_from_mart(client):
    response = client.get(
        "/api/lineage/table/mart.visits_daily", params={"direction": "up", "depth": 10}
    )
    assert response.status_code == 200
    body = response.json()
    ids = {node["id"] for node in body["nodes"]}
    assert "table:mart.visits_daily" in ids
    assert any(node_id.startswith("table:mongo.spa.") for node_id in ids)
    assert any(node_id.startswith("table:csv.") for node_id in ids)


def test_lineage_from_dag(client):
    response = client.get(
        "/api/lineage/dag/daily_ingest", params={"direction": "both", "depth": 2}
    )
    assert response.status_code == 200
    ids = {node["id"] for node in response.json()["nodes"]}
    assert "dag:daily_ingest" in ids
    assert "table:mongo.spa.clients" in ids
    assert "table:stg.clients" in ids


def test_path_exists(client):
    response = client.get(
        "/api/path", params={"from": f"table:{CORE_TABLE}", "to": f"table:{CORE_REPORT}"}
    )
    assert response.status_code == 200
    body = response.json()
    node_ids = [node["id"] for node in body["nodes"]]
    assert node_ids[0] == f"table:{CORE_TABLE}"
    assert node_ids[-1] == f"table:{CORE_REPORT}"
    assert len(body["edges"]) == len(node_ids) - 1
    for index, edge in enumerate(body["edges"]):
        assert {edge["source"], edge["target"]} == {node_ids[index], node_ids[index + 1]}


def test_path_disconnected_404(client, driver):
    try:
        with driver.session() as session:
            session.run(
                """
                CREATE (a:Table:TestTmp {fqn: 'testtmp.iso_a', name: 'Изолированная A',
                        system: 'generated', kind: 'source', description: '', rows_approx: 0})
                CREATE (b:Table:TestTmp {fqn: 'testtmp.iso_b', name: 'Изолированная B',
                        system: 'generated', kind: 'source', description: '', rows_approx: 0})
                """
            )
        response = client.get(
            "/api/path",
            params={"from": "table:testtmp.iso_a", "to": "table:testtmp.iso_b"},
        )
        assert response.status_code == 404
    finally:
        cleanup_test_nodes(driver)


def test_unknown_node_404(client):
    assert client.get("/api/node/table/no.such.table").status_code == 404
    assert client.get("/api/lineage/table/no.such.table").status_code == 404
    assert client.get("/api/lineage/scenario/no.such").status_code == 404


def test_depth_out_of_range_400(client):
    for depth in ("0", "11", "abc", "-1"):
        response = client.get(
            f"/api/lineage/table/{CORE_TABLE}", params={"depth": depth}
        )
        assert response.status_code == 400, depth


def test_search_cyrillic(client):
    response = client.get("/api/search", params={"q": "массаж"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    assert len(results) <= 20
    for node in results:
        assert node["id"].startswith(("table:", "dag:"))
        assert node["kind"] in {"table", "dag"}


def test_search_by_fqn(client):
    response = client.get("/api/search", params={"q": "appointments"})
    assert response.status_code == 200
    ids = {node["id"] for node in response.json()["results"]}
    assert "table:mongo.spa.appointments" in ids


def test_search_invalid_query_400(client):
    response = client.get("/api/search", params={"q": "("})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid search query"}


def test_search_auth_error_503(client):
    class BrokenAuthDriver:
        def session(self):
            raise neo4j.exceptions.AuthError("bad credentials")

    app.dependency_overrides[get_driver] = lambda: BrokenAuthDriver()
    try:
        response = client.get("/api/search", params={"q": "appointments"})
        assert response.status_code == 503
        assert response.json() == {"detail": "neo4j unavailable"}
    finally:
        app.dependency_overrides.clear()


def test_key_with_dots(client):
    response = client.get(f"/api/node/table/{CORE_TABLE}")
    assert response.status_code == 200
    assert response.json()["id"] == f"table:{CORE_TABLE}"


def test_subgraph_truncated(client, driver):
    try:
        with driver.session() as session:
            session.run(
                """
                CREATE (h:Table:TestTmp {fqn: 'testtmp.hub', name: 'Хаб',
                        system: 'generated', kind: 'source', description: '', rows_approx: 0})
                WITH h
                UNWIND range(1, 2500) AS i
                CREATE (l:Table:TestTmp {fqn: 'testtmp.leaf' + i, name: 'Лист ' + i,
                        system: 'generated', kind: 'source', description: '', rows_approx: 0})
                CREATE (h)-[:LOADS {mode: 'full'}]->(l)
                """
            )
        response = client.get(
            "/api/lineage/table/testtmp.hub", params={"direction": "down", "depth": 10}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["truncated"] is True
        assert len(body["nodes"]) <= 2000
        assert len(body["edges"]) <= 1999
        assert body["nodes"][0]["id"] == "table:testtmp.hub"
    finally:
        cleanup_test_nodes(driver)


def test_neo4j_unavailable_503(client):
    class BrokenDriver:
        def verify_connectivity(self):
            raise neo4j.exceptions.ServiceUnavailable("down")

        def session(self):
            raise neo4j.exceptions.ServiceUnavailable("down")

    app.dependency_overrides[get_driver] = lambda: BrokenDriver()
    try:
        health = client.get("/healthz")
        assert health.status_code == 503
        assert health.json() == {"neo4j": "down"}
        lineage = client.get(f"/api/lineage/table/{CORE_TABLE}")
        assert lineage.status_code == 503
        assert lineage.json() == {"detail": "neo4j unavailable"}
    finally:
        app.dependency_overrides.clear()