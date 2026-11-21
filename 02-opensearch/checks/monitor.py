"""Проверка экспортёра, Prometheus и Grafana."""

import os
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

from checks.client import Client


def nodes_with_data(response):
    if response.get("status") != "success":
        return set()
    return {
        item.get("metric", {}).get("node")
        for item in response.get("data", {}).get("result", [])
        if item.get("value")
    } - {None}


def run():
    ca = "/etc/checks/root-ca.crt"
    prom = Client("http://prometheus:9090")
    grafana = Client("http://grafana:3000", "admin", os.environ["GRAFANA_ADMIN_PASSWORD"])
    try:
        for node in ("os-hot", "os-warm"):
            client = Client(f"https://{node}:9200", "metricsAgent", os.environ["METRICSAGENT_PASSWORD"], ca)
            client.request("/_prometheus/metrics")
            print(f"  ok   экспортёр {node}")
        prom.request("/-/ready")
        query = urlencode({"query": 'up{job=~"opensearch-(hot|warm)"} == 1'})
        response = prom.json("/api/v1/query?" + query)
        jobs = {item.get("metric", {}).get("job") for item in response.get("data", {}).get("result", [])}
        if response.get("status") != "success" or jobs != {"opensearch-hot", "opensearch-warm"}:
            raise ValueError(f"цели Prometheus не готовы: {jobs}")
        metrics = prom.json("/api/v1/query?" + urlencode({"query": "opensearch_jvm_mem_heap_used_percent"}))
        if not {"os-hot", "os-warm"} <= nodes_with_data(metrics):
            raise ValueError("нет JVM-метрик обоих узлов")
        grafana.request("/api/health")
        dashboards = grafana.json("/api/search?" + urlencode({"query": "Coffee"}))
        if not any(item.get("uid") == "coffee-os" for item in dashboards):
            raise ValueError("дашборд coffee-os не найден")
    except (HTTPError, URLError, ValueError, KeyError, TypeError, TimeoutError) as error:
        print(f"МОНИТОРИНГ НЕ СОБРАН: {error}")
        return 1
    print("МОНИТОРИНГ РАБОТАЕТ")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
