"""Наблюдение жизненного цикла одного backing-индекса."""

import os
import time
from datetime import datetime
from urllib.error import HTTPError, URLError

from checks.client import Client
from checks.pipeline import run as check_pipeline


def is_warm_readonly(shards, settings, index):
    on_warm = any(s.get("prirep") == "p" and s.get("state") == "STARTED"
                  and s.get("node") == "os-warm" for s in shards)
    return on_warm and settings.get(index, {}).get("settings", {}).get("index.blocks.write") == "true"


def index_deleted(client, index):
    try:
        client.request(f"/{index}", "HEAD")
    except HTTPError as error:
        if error.code == 404:
            return True
        raise
    return False


def log(message):
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def run():
    if check_pipeline():
        return 1
    client = Client("https://os-hot:9200", "admin", os.environ["ADMIN_PASSWORD"],
                    "/etc/checks/root-ca.crt")
    try:
        initial = client.json("/_data_stream/logs")["data_streams"][0]["indices"][-1]
        index, index_uuid = initial["index_name"], initial["index_uuid"]
        log(f"Индекс записи: {index}, UUID {index_uuid}")
        deadline = time.monotonic() + 18 * 60
        rolled_over = warm = False
        while time.monotonic() < deadline:
            stream = client.json("/_data_stream/logs")["data_streams"][0]["indices"]
            if not rolled_over and stream[-1]["index_name"] != index:
                rolled_over = True
                log(f"ROLLOVER: создан {stream[-1]['index_name']}")
            present = any(item["index_name"] == index and item["index_uuid"] == index_uuid
                          for item in stream)
            if not present:
                if rolled_over and warm:
                    if not index_deleted(client, index):
                        raise ValueError(f"{index} отсутствует в потоке, но существует в кластере")
                    log(f"DELETE: {index} удалён")
                    print("ПОЛНЫЙ ЦИКЛ ISM ПРОЙДЕН")
                    return 0
                raise ValueError(f"{index} исчез до подтверждения warm/read-only")
            if rolled_over and not warm:
                shards = client.json(f"/_cat/shards/{index}?format=json&h=prirep,state,node")
                settings = client.json(f"/{index}/_settings?flat_settings=true")
                if is_warm_readonly(shards, settings, index):
                    warm = True
                    log(f"WARM: {index} на os-warm, запись запрещена")
            time.sleep(15)
        raise TimeoutError("цикл ISM не завершился за 18 минут")
    except (HTTPError, URLError, ValueError, KeyError, IndexError, TypeError, TimeoutError) as error:
        print(f"ЦИКЛ ISM НЕ ПРОЙДЕН: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
