"""Проверка состояния Redis через redis-cli внутри контейнера redis (docker compose exec)."""

import subprocess

from .client import env

FAILURES = []

COMPOSE_PROJECT_DIR = "."


def parse_scan_output(raw):
    return [line.strip() for line in raw.splitlines() if line.strip().startswith("ratelimit:client:")]


def parse_pttl(raw):
    try:
        return int(raw.strip())
    except ValueError:
        return None


def redis_cli(*args):
    # redis-контейнер сам держит REDIS_PASSWORD в окружении; REDISCLI_AUTH вместо -a —
    # пароль не попадает в аргументы командной строки и не требует экранирования кавычек.
    inner = 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --no-auth-warning ' + " ".join(args)
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "sh", "-c", inner],
        capture_output=True, text=True, cwd=COMPOSE_PROJECT_DIR, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"redis-cli failed: {result.stderr.strip()}")
    return result.stdout


def run_redis_checks():
    keys = parse_scan_output(redis_cli("--scan", "--pattern", "'ratelimit:client:*'"))
    if not keys:
        print("[WARN] redis.keys — нет ключей ratelimit:client:* (после нагрузки должны быть)")
    else:
        print(f"[INFO] redis.keys — найдено ключей: {len(keys)}")

    stale_ttl = []
    for key in keys[:20]:
        pttl = parse_pttl(redis_cli("PTTL", f"'{key}'"))
        if pttl is None or pttl <= 0:
            stale_ttl.append((key, pttl))
    ok_ttl = not stale_ttl
    status = "PASS" if (keys and ok_ttl) else ("PASS" if not keys else "FAIL")
    if keys and not ok_ttl:
        print(f"[{status}] redis.ttl — ключи без TTL: {stale_ttl[:5]}")
        FAILURES.append("redis.ttl")
    else:
        print(f"[{status}] redis.ttl" + ("" if keys else " — ключей нет, проверка TTL пропущена"))

    if keys:
        fields_raw = redis_cli("HKEYS", f"'{keys[0]}'")
        fields = {f.strip() for f in fields_raw.splitlines() if f.strip()}
        ok_fields = {"tokens", "ts"} <= fields
        print(f"[{'PASS' if ok_fields else 'FAIL'}] redis.hash-fields — поля: {sorted(fields)}")
        if not ok_fields:
            FAILURES.append("redis.hash-fields")

    return FAILURES


if __name__ == "__main__":
    import sys

    sys.exit(1 if run_redis_checks() else 0)
