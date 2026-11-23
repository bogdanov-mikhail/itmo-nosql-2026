"""Проверки API живого стенда: 401 без/с чужим ключом, 200 с валидным, 429 с различимыми заголовками."""

import time

from .client import HttpClient, env

FAILURES = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def classify_decision(response):
    """Возвращает (код, причину отказа) по заголовку или None-причину для 2xx."""
    reason = response.header("X-Rate-Limit-Reason")
    return response.status, reason


def run_api_checks(smoke=False):
    base = env("APP_BASE_URL", "http://127.0.0.1:8080")
    free_key = env("API_KEY_FREE")
    client = HttpClient(base)

    if not free_key:
        check("api.env", False, "API_KEY_FREE не задан (окружение или .env)")
        return FAILURES

    missing = client.get("/courses")
    check("api.401.missing-key", missing.status == 401, f"получен {missing.status}")

    unknown = client.get("/courses", api_key="definitely-not-a-key")
    check("api.401.unknown-key", unknown.status == 401, f"получен {unknown.status}")

    ok = client.get("/courses", api_key=free_key)
    check("api.200.valid-key", ok.status == 200, f"получен {ok.status}: {ok.body[:120]}")

    if ok.status == 200:
        single = client.get("/courses/1", api_key=free_key)
        check("api.200.course-by-id", single.status == 200, f"получен {single.status}")
        search = client.get("/courses/search?q=Kotlin", api_key=free_key)
        check("api.200.search", search.status == 200 and "Kotlin" in search.body,
              f"получен {search.status}")

    if smoke:
        # Smoke не должен выжигать бакет надолго: умеренный burst, ожидание 429 client.
        responses = []
        for _ in range(30):
            responses.append(client.get("/courses", api_key=free_key))
    else:
        responses = []
        for _ in range(60):
            responses.append(client.get("/courses", api_key=free_key))
        time.sleep(1.2)
        for _ in range(60):
            responses.append(client.get("/courses", api_key=free_key))

    rejected_client = [r for r in responses if r.status == 429 and r.header("X-Rate-Limit-Reason") == "client"]
    check("api.429.client-reason", len(rejected_client) > 0,
          f"нет 429 с X-Rate-Limit-Reason: client (статусы: {sorted(set(r.status for r in responses))})")

    if rejected_client:
        sample = rejected_client[0]
        retry_after = sample.header("Retry-After")
        try:
            retry_ok = int(retry_after) >= 0
        except (TypeError, ValueError):
            retry_ok = False
        check("api.429.retry-after", retry_ok, f"Retry-After={retry_after!r}")

    platform_rejects = [r for r in responses if r.status == 429 and r.header("X-Rate-Limit-Reason") == "platform"]
    if smoke:
        check("api.smoke.no-platform-rejects", len(platform_rejects) == 0,
              f"в smoke ожидается только client-квота, platform-отказов: {len(platform_rejects)}")

    server_errors = [r for r in responses if r.status >= 500]
    check("api.no-5xx", len(server_errors) == 0, f"5xx ответов: {len(server_errors)}")

    return FAILURES


if __name__ == "__main__":
    import sys

    smoke = "--smoke" in sys.argv
    sys.exit(1 if run_api_checks(smoke=smoke) else 0)
