COMPOSE = docker compose --env-file .env
SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c
CHECK_ENV = APP_BASE_URL=http://127.0.0.1:18080 PROMETHEUS_URL=http://127.0.0.1:19090 GRAFANA_URL=http://127.0.0.1:13000

.PHONY: up down status build logs smoke verify monitor-check unit-tests load chaos-test

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

unit-tests:
	python3 -m unittest discover -s tests -v

smoke:
	$(CHECK_ENV) python3 checks/run.py --api --smoke --redis

monitor-check:
	$(CHECK_ENV) python3 checks/run.py --monitor

chaos-test:
	$(CHECK_ENV) python3 checks/run.py --chaos

verify: up
	$(CHECK_ENV) python3 checks/run.py --api --redis --monitor

load:
	@mkdir -p load/results
	@if [ -z "$(PROFILE)" ]; then echo "использование: make load PROFILE=smoke|burst|fair|platform"; exit 2; fi
	@if [ "$(PROFILE)" = "platform" ]; then \
	  echo "[load] временно повышаю тариф standard для app (per-client не должен резать раньше платформы)"; \
	  RATELIMIT_STANDARD_RATE=1000 RATELIMIT_STANDARD_CAPACITY=2000 $(COMPOSE) up -d app --wait >/dev/null; \
	fi
	$(COMPOSE) run --rm --no-deps k6 run /load/$(PROFILE).js 2>&1 | tee load/results/$(PROFILE)-`date +%Y%m%d-%H%M%S`.txt
	@RC=$$?; \
	if [ "$(PROFILE)" = "platform" ]; then \
	  echo "[load] возвращаю конфиг app (тарифы из .env)"; \
	  $(COMPOSE) up -d app --wait >/dev/null; \
	fi; \
	exit $$RC
