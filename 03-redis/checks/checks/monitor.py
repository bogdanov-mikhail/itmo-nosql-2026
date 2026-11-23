"""Проверки мониторинга: цели Prometheus, метрики приложения через Prometheus API, Grafana-datasource."""

import json
import urllib.request

from .client import env

FAILURES = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def fetch_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_targets(payload):
    """{job: health} по activeTargets ответа /api/v1/targets."""
    return {t["labels"].get("job", "?"): t.get("health", "") for t in payload["data"]["activeTargets"]}


def query_result_count(payload):
    return len(payload["data"]["result"])


def query_prom(prometheus, expr):
    from urllib.parse import quote

    return fetch_json(f"{prometheus}/api/v1/query?query={quote(expr)}")


def query_prom_range(prometheus, expr, minutes=15, step=60):
    from urllib.parse import quote
    import time

    now = int(time.time())
    url = (
        f"{prometheus}/api/v1/query_range?query={quote(expr)}"
        f"&start={now - minutes * 60}&end={now}&step={step}"
    )
    return fetch_json(url)


def range_series_count(payload):
    return len(payload["data"]["result"])


def run_monitor_checks():
    prometheus = env("PROMETHEUS_URL", "http://127.0.0.1:19090")
    grafana = env("GRAFANA_URL", "http://127.0.0.1:13000")

    try:
        targets = parse_targets(fetch_json(f"{prometheus}/api/v1/targets"))
    except Exception as e:
        check("monitor.prometheus", False, f"нет ответа Prometheus API: {e}")
        return FAILURES

    for job in ("app", "redis"):
        check(f"monitor.target-up.{job}", targets.get(job) == "up",
              f"job={job} health={targets.get(job, 'нет в целях')}")

    try:
        app_up = query_prom(prometheus, "kora_up")
        check("monitor.series.kora_up", query_result_count(app_up) > 0,
              "нет kora_up — Prometheus не видит приложение")
        decisions = query_prom_range(prometheus, "ratelimit_decisions_total")
        check("monitor.series.ratelimit_decisions", range_series_count(decisions) > 0,
              "рядов ratelimit_decisions_total не было за последние 15 минут (счётчик появляется после первого запроса; сначала make smoke или load)")
        errors = query_prom(prometheus, "ratelimit_redis_errors_total")
        check("monitor.series.ratelimit_redis_errors", query_result_count(errors) > 0,
              "нет ряда ratelimit_redis_errors_total (регистрация счётчика)")
        redis_mem = query_prom(prometheus, "redis_memory_used_bytes")
        check("monitor.series.redis_exporter", query_result_count(redis_mem) > 0,
              "redis_exporter не отдаёт метрики в Prometheus")
    except Exception as e:
        check("monitor.queries", False, f"ошибка запроса: {e}")

    try:
        import base64
        from urllib.parse import quote

        token = base64.b64encode(f"admin:{env('GRAFANA_ADMIN_PASSWORD')}".encode()).decode()
        request = urllib.request.Request(f"{grafana}/api/datasources")
        request.add_header("Authorization", f"Basic {token}")
        sources = fetch_json_or_request(request)
        names = [s.get("name") for s in sources]
        check("monitor.grafana.datasource", "Prometheus" in names, f"датасорсы: {names}")

        search = fetch_json_or_request_authed(
            f"{grafana}/api/search?query={quote('Redis Rate Limiter')}",
            token,
        )
        dashboards = [d.get("title") for d in search]
        check("monitor.grafana.dashboard", "Redis Rate Limiter — ЛР-3" in dashboards,
              f"дашборд не найден, поиск вернул: {dashboards}")
    except Exception as e:
        check("monitor.grafana", False, f"нет ответа Grafana API: {e}")

    return FAILURES


def fetch_json_or_request_authed(url, basic_token):
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Basic {basic_token}")
    return fetch_json_or_request(request)


def fetch_json_or_request(request):
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    import sys

    sys.exit(1 if run_monitor_checks() else 0)
