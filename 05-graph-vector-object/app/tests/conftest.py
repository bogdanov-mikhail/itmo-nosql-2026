import os

import neo4j
import pytest


@pytest.fixture(scope="session")
def driver():
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    password = os.environ["NEO4J_PASSWORD"]
    d = neo4j.GraphDatabase.driver(uri, auth=("neo4j", password))
    yield d
    d.close()