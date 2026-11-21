"""Проверка ролевой модели реальными запросами."""

import json
import os
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

from checks.client import Client


def bulk_succeeded(response):
    items = response.get("items", [])
    return (
        response.get("errors") is False
        and len(items) == 1
        and items[0].get("create", {}).get("status") == 201
    )


def deletion_denied(response):
    return (response.get("accessAllowed") is False
            and "indices:admin/data_stream/delete" in response.get("missingPrivileges", []))


def run():
    url = "https://os-hot:9200"
    ca = "/etc/checks/root-ca.crt"
    password_names = {
        "admin": "ADMIN_PASSWORD",
        "logshipper": "LOGSHIPPER_PASSWORD",
        "analyst01": "ANALYST_PASSWORD",
        "metricsAgent": "METRICSAGENT_PASSWORD",
    }
    clients = {
        name: Client(url, name, os.environ[var], ca)
        for name, var in password_names.items()
    }
    anonymous = Client(url, ca_file=ca)
    try:
        stream = clients["admin"].json("/_data_stream/logs")
        write_index = stream["data_streams"][0]["indices"][-1]["index_name"]
    except (HTTPError, URLError, ValueError, KeyError, IndexError, TimeoutError) as error:
        print(f"МАТРИЦА НЕ СОШЛАСЬ: поток logs недоступен: {error}")
        return 1

    passed = failed = 0

    def check(name, client, path, expected, method="GET", data=None, content_type="application/json"):
        nonlocal passed, failed
        try:
            status, body = client.request(path, method, data, content_type)
        except HTTPError as error:
            status, body = error.code, ""
        except (URLError, TimeoutError) as error:
            print(f"  FAIL {name}: ошибка соединения: {error}")
            failed += 1
            return
        good = status == expected
        if good and content_type == "application/x-ndjson":
            try:
                good = bulk_succeeded(json.loads(body))
            except (ValueError, AttributeError):
                good = False
        print(f"  {'ok  ' if good else 'FAIL'} {name} [HTTP {status}, ожидалось {expected}]")
        passed += int(good)
        failed += int(not good)

    shipper = clients["logshipper"]
    analyst = clients["analyst01"]
    monitor = clients["metricsAgent"]
    document = {"@timestamp": datetime.now(timezone.utc).isoformat(), "matrix": "rbac-check"}
    bulk = '{"create":{"_index":"logs"}}\n' + json.dumps(document) + "\n"
    probe_id = "rbac-absent-" + uuid.uuid4().hex
    check("анонимный доступ", anonymous, "/", 401)
    check("запись в logs", shipper, "/logs/_bulk", 200, "POST", bulk, "application/x-ndjson")
    check("чтение logshipper", shipper, "/logs/_search", 403)
    try:
        simulation = clients["admin"].json("/_cluster/health?perform_permission_check=true")
        if simulation.get("accessAllowed") is not True:
            raise ValueError("проверка разрешений недоступна")
        result = shipper.json("/_data_stream/logs?perform_permission_check=true", "DELETE")
        if not deletion_denied(result):
            raise ValueError("запрет удаления потока не подтверждён")
        print("  ok   удаление потока отклонено (проверка разрешений)")
        passed += 1
    except (HTTPError, URLError, ValueError, TimeoutError) as error:
        print(f"  FAIL проверка удаления потока: {error}")
        failed += 1
    check("удаление документа", shipper, f"/{write_index}/_doc/{probe_id}", 403, "DELETE")
    check("изменение документа", shipper, f"/{write_index}/_update/{probe_id}",
          403, "POST", {"doc": {"matrix": "rbac-check"}})
    check("чтение analyst01", analyst, "/logs/_search", 200)
    check("запись analyst01", analyst, "/logs/_doc", 403, "POST", {})
    check("метрики analyst01", analyst, "/_cluster/health", 403)
    check("состояние кластера", monitor, "/_cluster/health", 200)
    check("метрики os-hot", monitor, "/_prometheus/metrics", 200)
    warm = Client("https://os-warm:9200", "metricsAgent", os.environ["METRICSAGENT_PASSWORD"], ca)
    check("метрики os-warm", warm, "/_prometheus/metrics", 200)
    check("запись metricsAgent", monitor, "/logs/_doc", 403, "POST", {})

    print(f"\nитог: ok={passed} fail={failed}")
    print("МАТРИЦА СОШЛАСЬ" if not failed else "МАТРИЦА НЕ СОШЛАСЬ")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(run())
