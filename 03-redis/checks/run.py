"""Точка входа проверок живого стенда (запускается с хоста через make)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks import api, chaos, monitor, redis_state  # noqa: E402


def main(argv):
    failed = []
    ran = False

    flags = ("--api", "--redis", "--monitor", "--all", "--chaos")
    if not any(f in argv for f in flags):
        argv = argv + ["--api"]

    if "--api" in argv or "--all" in argv:
        ran = True
        failed += api.run_api_checks(smoke="--smoke" in argv)
    if "--redis" in argv or "--all" in argv:
        ran = True
        failed += redis_state.run_redis_checks()
    if "--monitor" in argv or "--all" in argv:
        ran = True
        failed += monitor.run_monitor_checks()
    if "--chaos" in argv:
        ran = True
        failed += chaos.run_chaos_checks()

    if not ran:
        print("использование: python -m checks.run [--api [--smoke]] [--redis] [--monitor] [--all]")
        return 2

    if failed:
        print(f"ИТОГ: ПРОВАЛЕНО проверок: {len(failed)} — {', '.join(failed)}")
        return 1
    print("ИТОГ: все проверки зелёные")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
