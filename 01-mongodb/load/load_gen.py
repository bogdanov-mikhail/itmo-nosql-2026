#!/usr/bin/env python3
"""Генератор нагрузки для учебной базы spa: ramp-up + устойчивая фаза.

Операции под пользователем frontdesk01 (роли frontDeskOperator):
  insert в appointments (документ с payload ~1.5 KiB),
  find по services (по индексируемому коду),
  update статуса записи в appointments.
Креды — через env SPA_LOAD_CREDS (JSON). Счётчики — в stdout последней строкой
JSON и в /tmp/spa-load-report.json.
"""
import datetime
import json
import os
import random
import string
import sys
import threading
import time
from urllib.parse import quote_plus

from pymongo import MongoClient

RAMP_SECONDS = 30
STEADY_SECONDS = 120
MAX_THREADS = 4
SERVICE_CODES = ["back-60", "neck-30", "sport-90", "aroma-60", "foot-45", "kids-30"]
CLIENT_CODES = [f"c-{i:02d}" for i in range(1, 9)]
MASTER_CODES = [f"m-{i:02d}" for i in range(1, 5)]

counters = {"inserted": 0, "found": 0, "updated": 0}
lock = threading.Lock()


def make_payload(size=1500):
    return "".join(random.choices(string.ascii_letters + string.digits, k=size))


def worker(thread_id, stop_at, creds):
    uri = (
        f"mongodb://{quote_plus(creds['user'])}:{quote_plus(creds['password'])}"
        "@127.0.0.1:27017/spa?authSource=spa"
    )
    db = MongoClient(uri).get_database("spa")
    seq = 0
    while time.time() < stop_at:
        seq += 1
        try:
            code = f"load-{thread_id}-{seq}-{int(time.time())}"
            db.appointments.insert_one({
                "code": code,
                "client_code": random.choice(CLIENT_CODES),
                "master_code": random.choice(MASTER_CODES),
                "service_code": random.choice(SERVICE_CODES),
                "starts_at": datetime.datetime.utcnow() + datetime.timedelta(hours=random.randint(1, 72)),
                "status": "booked",
                "price": random.choice([1900, 2200, 2800, 3500, 4000, 4800]),
                "notes": make_payload(),
                "load_probe": True,
            })
            with lock:
                counters["inserted"] += 1
            db.services.find_one({"code": random.choice(SERVICE_CODES)})
            with lock:
                counters["found"] += 1
            if seq % 3 == 0:
                db.appointments.update_one(
                    {"code": code}, {"$set": {"status": random.choice(["done", "booked", "cancelled"])}}
                )
                with lock:
                    counters["updated"] += 1
        except Exception as exc:  # продолжаем при разовых сбоях, но не молчим
            print(f"thread-{thread_id}: {exc}", file=sys.stderr)


def main():
    creds = json.loads(os.environ["SPA_LOAD_CREDS"])
    start = time.time()
    stop_all = start + RAMP_SECONDS + STEADY_SECONDS

    threads = []
    for tid in range(1, MAX_THREADS + 1):
        t = threading.Thread(target=worker, args=(tid, stop_all, creds), daemon=True)
        if tid > 1:
            # ramp-up: поток добавляется каждые ~10 секунд
            while time.time() < start + (tid - 1) * (RAMP_SECONDS / (MAX_THREADS - 1)):
                time.sleep(0.5)
        t.start()
        threads.append(t)
        print(f"thread-{tid} started at +{time.time() - start:.0f}s", flush=True)

    for t in threads:
        t.join()

    report = {
        **counters,
        "elapsed_seconds": round(time.time() - start, 1),
        "threads": MAX_THREADS,
        "ramp_seconds": RAMP_SECONDS,
        "steady_seconds": STEADY_SECONDS,
    }
    with open("/tmp/spa-load-report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh)
    print("LOAD-REPORT " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
