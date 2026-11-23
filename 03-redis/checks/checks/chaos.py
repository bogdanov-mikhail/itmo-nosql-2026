"""Негативный сценарий: Redis недоступен (per-client fail-open + глобальный fail-closed) и восстановление."""

import subprocess
import time

from . import monitor
from .client import HttpClient, env

FAILURES = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def compose(*args):
    result = subprocess.run(
        ["docker", "compose", "--env-file", ".env", *args],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def redis_errors_total(prometheus_url):
    payload = monitor.query_prom(prometheus_url, "sum(ratelimit_redis_errors_total)")
    result = payload["data"]["result"]
    return float(result[0]["value"][1]) if result else 0.0


def run_chaos_checks():
    base = env("APP_BASE_URL", "http://127.0.0.1:18080")
    prometheus = env("PROMETHEUS_URL", "http://127.0.0.1:19090")
    free_key = env("API_KEY_FREE")
    client = HttpClient(base)

    if not free_key:
        check("chaos.env", False, "API_KEY_FREE не задан")
        return FAILURES

    print("[chaos] фаза 1: живой Redis — базовый уровень")
    ok_before = [client.get("/courses", api_key=free_key).status for _ in range(3)]
    check("chaos.phase1.all-200", all(s == 200 for s in ok_before), f"статусы: {ok_before}")
    time.sleep(6)
    errors_before = redis_errors_total(prometheus)
    print(f"[INFO] ratelimit_redis_errors_total до остановки: {errors_before}")

    print("[chaos] фаза 2: останавливаю redis")
    compose("stop", "redis")
    time.sleep(2)

    statuses = [client.get("/courses", api_key=free_key).status for _ in range(5)]
    check("chaos.phase2.all-503", all(s == 503 for s in statuses),
          f"ожидались все 503 (fail-closed глобальной квоты), получено: {statuses}")

    time.sleep(8)
    errors_after = redis_errors_total(prometheus)
    check("chaos.phase2.errors-increase", errors_after >= errors_before + 5,
          f"ratelimit_redis_errors_total: {errors_before} -> {errors_after} (ожидалось +>=5: по одному на запрос в fail-open пути)")

    print("[chaos] фаза 3: поднимаю redis, проверяю восстановление")
    compose("up", "-d", "--wait", "redis")
    time.sleep(3)

    recovered = []
    for attempt in range(10):
        status = client.get("/courses", api_key=free_key).status
        recovered.append(status)
        if status == 200:
            break
        time.sleep(2)
    check("chaos.phase3.back-to-200", recovered[-1] == 200, f"статусы после старта: {recovered}")

    time.sleep(6)
    errors_final = redis_errors_total(prometheus)
    # допускаем +1: первый запрос после старта Redis может застать ещё не
    # переподключившееся соединение Lettuce — это одна честная ошибка, а не рост
    check("chaos.phase3.errors-stable", errors_final <= errors_after + 1,
          f"после восстановления счётчик почти не растёт: {errors_after} -> {errors_final}")

    print("[INFO] состояние бакетов после простоя обнуляется TTL-окном — ожидаемое поведение")
    return FAILURES


if __name__ == "__main__":
    import sys

    sys.exit(1 if run_chaos_checks() else 0)
