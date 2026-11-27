import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import neo4j
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

import graph

REQUEST_DURATION = Histogram(
    "api_request_duration_seconds",
    "Длительность HTTP-запроса",
    ["endpoint", "status"],
)
REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Количество HTTP-запросов",
    ["endpoint", "status"],
)
NEO4J_ERRORS = (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError)


def unavailable():
    return HTTPException(status_code=503, detail="neo4j unavailable")


@asynccontextmanager
async def lifespan(application):
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
    application.state.driver = driver
    try:
        yield
    finally:
        driver.close()


app = FastAPI(title="SPA Data Lineage", lifespan=lifespan)


def get_driver(request: Request):
    return request.app.state.driver


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)
        duration = time.perf_counter() - started
        REQUEST_DURATION.labels(endpoint=endpoint, status=str(status)).observe(duration)
        REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(status)).inc()


@app.get("/healthz")
def healthz(driver=Depends(get_driver)):
    try:
        driver.verify_connectivity()
    except NEO4J_ERRORS:
        return JSONResponse(status_code=503, content={"neo4j": "down"})
    return {"neo4j": "up"}


@app.get("/api/search")
def search(q: str = "", driver=Depends(get_driver)):
    if not q.strip():
        return {"query": q, "results": []}
    try:
        results = graph.search_nodes(driver, q.strip())
    except neo4j.exceptions.AuthError:
        raise unavailable()
    except neo4j.exceptions.ClientError:
        raise HTTPException(status_code=400, detail="invalid search query")
    except NEO4J_ERRORS:
        raise unavailable()
    return {"query": q, "results": results}


@app.get("/api/node/{kind}/{key}")
def node(kind: str, key: str, driver=Depends(get_driver)):
    try:
        found = graph.get_node(driver, kind, key)
    except NEO4J_ERRORS:
        raise unavailable()
    if found is None:
        raise HTTPException(status_code=404, detail="node not found")
    return found


@app.get("/api/lineage/{kind}/{key}")
def lineage(
    kind: str,
    key: str,
    direction: str = "both",
    depth: Optional[str] = None,
    driver=Depends(get_driver),
):
    if direction not in graph.DIRECTIONS:
        raise HTTPException(status_code=400, detail="direction must be up, down or both")
    try:
        depth_value = graph.parse_depth(depth)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    try:
        subgraph = graph.lineage_subgraph(driver, kind, key, direction, depth_value)
    except NEO4J_ERRORS:
        raise unavailable()
    if subgraph is None:
        raise HTTPException(status_code=404, detail="node not found")
    return subgraph


@app.get("/api/path")
def path(
    from_id: str = Query(alias="from"),
    to_id: str = Query(alias="to"),
    driver=Depends(get_driver),
):
    try:
        found = graph.shortest_path(driver, from_id, to_id)
    except NEO4J_ERRORS:
        raise unavailable()
    if found is None:
        if graph.parse_node_id(from_id) is None or graph.parse_node_id(to_id) is None:
            raise HTTPException(status_code=400, detail="invalid node id")
        raise HTTPException(status_code=404, detail="path not found")
    return found


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="static",
)