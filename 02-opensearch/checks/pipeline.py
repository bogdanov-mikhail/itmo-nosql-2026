"""Проверка пути от nginx до data stream."""

import os
import time
import uuid
from urllib.error import HTTPError, URLError

from checks.client import Client


def missing_requests(expected, received):
    return expected - set(received)


def run():
    nginx = Client("http://nginx:80")
    opensearch = Client("https://os-hot:9200", "admin", os.environ["ADMIN_PASSWORD"],
                        "/etc/checks/root-ca.crt")
    marker = "probe-" + uuid.uuid4().hex
    expected = {f"cb={marker}-{i}" for i in range(200)}
    try:
        for arg in expected:
            nginx.request("/?" + arg)
        print("  ok   nginx: отправлено 200 запросов")
        query = {"size": 300, "_source": ["args"],
                 "query": {"prefix": {"args": f"cb={marker}-"}}}
        missing = expected
        deadline = time.monotonic() + 120
        while missing and time.monotonic() < deadline:
            result = opensearch.json("/logs/_search", "POST", query)
            received = [hit["_source"]["args"] for hit in result["hits"]["hits"]]
            missing = missing_requests(expected, received)
            if missing:
                time.sleep(3)
        if missing:
            raise ValueError(f"не доставлено {len(missing)} из 200 запросов")
        mapping = opensearch.json("/logs/_mapping")
        if not any("request_time" in index.get("mappings", {}).get("properties", {})
                   for index in mapping.values()):
            raise ValueError("нет поля request_time в маппинге")
        explain = opensearch.json("/_plugins/_ism/explain/logs")
        if not any(isinstance(value, dict) and value.get("policy_id") == "logs-lifecycle"
                   for value in explain.values()):
            raise ValueError("политика ISM не применена")
        stream = opensearch.json("/_data_stream/logs")
        index = stream["data_streams"][0]["indices"][-1]["index_name"]
        shards = opensearch.json(f"/_cat/shards/{index}?format=json&h=prirep,state,node")
        if not any(s["prirep"] == "p" and s["state"] == "STARTED" and s["node"] == "os-hot"
                   for s in shards):
            raise ValueError(f"первичный шард {index} не активен на os-hot")
    except (HTTPError, URLError, ValueError, KeyError, IndexError, TypeError, TimeoutError) as error:
        print(f"ПАЙПЛАЙН НЕ ПРОШЁЛ: {error}")
        return 1
    print(f"  ok   доставлены все 200 уникальных запросов; индекс записи {index} на os-hot")
    print("ПАЙПЛАЙН РАБОТАЕТ")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
