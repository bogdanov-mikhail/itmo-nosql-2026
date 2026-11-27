SHELL := /bin/bash
COMPOSE := docker compose
NEO4J_PASSWORD := $(shell grep -h '^NEO4J_PASSWORD=' .env 2>/dev/null | cut -d= -f2-)
MEASUREMENTS_DIR ?= $(HOME)/IdeaProjects/itmo-sem-3/subjects/nosql-databases/05-graph-vector-object/measurements

.PHONY: env up down status logs seed seed-scale api-check monitor-check load-smoke load-demo load-scale verify ui test test-integration

env:
	@if [ -f .env ]; then \
		echo ".env уже есть — не меняю"; \
	else \
		printf 'NEO4J_PASSWORD=%s\n' "$$(openssl rand -hex 16)" > .env; \
		echo ".env создан, пароль сгенерирован"; \
	fi

up: env
	@docker info >/dev/null 2>&1 || { echo "Docker не запущен: включите Docker Desktop и повторите"; exit 1; }
	$(COMPOSE) up -d --wait --build
	$(COMPOSE) ps

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

seed:
	$(COMPOSE) run --rm --build seed

seed-scale:
	$(COMPOSE) run --rm --build seed python seed.py --scale --tables 5000 --dags 1500

api-check:
	@base=http://127.0.0.1:28080; failures=0; tmp=/tmp/lab05-api-check; \
	pass() { printf '%-44s %s\n' "$$1" "OK"; }; \
	fail() { printf '%-44s %s\n' "$$1" "FAIL: $$2"; failures=$$((failures+1)); }; \
	printf '%-44s %s\n' "проверка" "результат"; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/healthz"); \
	if [ "$$code" = 200 ] && grep -q '"neo4j":"up"' $$tmp; then pass "/healthz"; else fail "/healthz" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/lineage/table/mongo.spa.appointments?direction=down&depth=3"); \
	if [ "$$code" = 200 ] && grep -q '"dag:daily_ingest"' $$tmp; then pass "lineage вниз от источника"; else fail "lineage вниз от источника" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/lineage/table/mart.visits_daily?direction=up&depth=10"); \
	if [ "$$code" = 200 ] && grep -q '"table:mongo.spa.clients"' $$tmp; then pass "lineage вверх от марта"; else fail "lineage вверх от марта" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/path?from=table:mongo.spa.appointments&to=table:report.revenue_dashboard"); \
	if [ "$$code" = 200 ] && grep -q '"table:report.revenue_dashboard"' $$tmp; then pass "path источник → отчёт"; else fail "path источник → отчёт" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/node/table/no.such.table"); \
	if [ "$$code" = 404 ]; then pass "неизвестный узел → 404"; else fail "неизвестный узел → 404" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/lineage/table/mongo.spa.appointments?depth=11"); \
	if [ "$$code" = 400 ]; then pass "depth=11 → 400"; else fail "depth=11 → 400" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' --get --data-urlencode "q=массаж" "$$base/api/search"); \
	if [ "$$code" = 200 ] && grep -q '"results":\[{' $$tmp; then pass "search «массаж»"; else fail "search «массаж»" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' --get --data-urlencode "q=(" "$$base/api/search"); \
	if [ "$$code" = 400 ]; then pass "невалидный поиск → 400"; else fail "невалидный поиск → 400" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/metrics"); \
	if [ "$$code" = 200 ] && grep -q 'api_request_duration_seconds' $$tmp; then pass "/metrics"; else fail "/metrics" "код $$code"; fi; \
	code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/node/table/gen_s42.t00000"); \
	if [ "$$code" = 200 ]; then \
		code=$$(curl -s -o $$tmp -w '%{http_code}' "$$base/api/path?from=table:mongo.spa.appointments&to=table:gen_s42.t00000"); \
		if [ "$$code" = 404 ]; then pass "path между компонентами → 404"; else fail "path между компонентами → 404" "код $$code"; fi; \
	else printf '%-44s %s\n' "path между компонентами → 404" "SKIP: масштаб не загружен"; fi; \
	rm -f $$tmp; \
	if [ $$failures -ne 0 ]; then echo "провалов: $$failures"; exit 1; fi

monitor-check:
	@prom=http://127.0.0.1:29090; graf=http://127.0.0.1:23000; failures=0; tmp=/tmp/lab05-monitor-check; \
	pass() { printf '%-46s %s\n' "$$1" "OK"; }; \
	fail() { printf '%-46s %s\n' "$$1" "FAIL: $$2"; failures=$$((failures+1)); }; \
	printf '%-46s %s\n' "проверка" "результат"; \
	code=$$(curl -s -o /dev/null -w '%{http_code}' "$$prom/-/healthy"); \
	if [ "$$code" = 200 ]; then pass "Prometheus /-/healthy"; else fail "Prometheus /-/healthy" "код $$code"; fi; \
	curl -s "$$prom/api/v1/targets" > $$tmp; \
	if python3 -c "import json; d=json.load(open('$$tmp'))['data']['activeTargets']; assert sorted((t['labels']['job'], t['health']) for t in d)==[('api','up'),('neo4j','up')]"; then pass "цели api и neo4j в состоянии up"; else fail "цели api и neo4j в состоянии up" "не все up"; fi; \
	curl -s "$$prom/api/v1/label/__name__/values" > $$tmp; \
	if python3 -c "import json; s=set(json.load(open('$$tmp'))['data']); need={'neo4j_dbms_page_cache_hit_ratio','neo4j_dbms_vm_heap_used','neo4j_database_neo4j_transaction_committed_total','neo4j_database_neo4j_check_point_duration','api_request_duration_seconds_bucket','api_requests_total'}; miss=need-s; assert not miss, miss"; then pass "нужные серии есть в Prometheus"; else fail "нужные серии есть в Prometheus" "серий не хватает"; fi; \
	curl -s "$$graf/api/health" > $$tmp; \
	if python3 -c "import json; assert json.load(open('$$tmp'))['database']=='ok'"; then pass "Grafana /api/health"; else fail "Grafana /api/health" "database не ok"; fi; \
	curl -s "$$graf/api/datasources/uid/prometheus/health" > $$tmp; \
	if python3 -c "import json; assert json.load(open('$$tmp'))['status']=='OK'"; then pass "datasource Prometheus отвечает"; else fail "datasource Prometheus отвечает" "status не OK"; fi; \
	curl -s "$$graf/api/search?query=Lineage" > $$tmp; \
	if python3 -c "import json; a=json.load(open('$$tmp')); assert any('Lineage' in x['title'] for x in a)"; then pass "дашборд Lineage в Grafana"; else fail "дашборд Lineage в Grafana" "не найден"; fi; \
	curl -s "$$graf/api/dashboards/uid/lineage-neo4j" > $$tmp; \
	if python3 -c "import json; d=json.load(open('$$tmp'))['dashboard']; assert d['title']=='Lineage — Neo4j'; assert len(d['panels'])>=8, len(d['panels'])"; then pass "дашборд: заголовок и ≥8 панелей"; else fail "дашборд: заголовок и ≥8 панелей" "структура не та"; fi; \
	rm -f $$tmp; \
	if [ $$failures -ne 0 ]; then echo "провалов: $$failures"; exit 1; fi

load-smoke:
	$(COMPOSE) run --rm --no-deps -e MODE=smoke k6

load-demo:
	@set -o pipefail; mkdir -p "$(MEASUREMENTS_DIR)"; $(COMPOSE) run --rm --no-deps k6 2>&1 | tee "$(MEASUREMENTS_DIR)/load-demo.txt"

load-scale:
	@set -o pipefail; mkdir -p "$(MEASUREMENTS_DIR)"; $(COMPOSE) run --rm --no-deps -e MODE=scale k6 2>&1 | tee "$(MEASUREMENTS_DIR)/load-scale.txt"

verify:
	@set -e; log=/tmp/lab05-verify-stage.log; failures=0; \
	stage() { name="$$1"; shift; printf '%s ... ' "$$name"; if "$$@" >$$log 2>&1; then echo OK; else echo FAIL; tail -20 $$log; exit 1; fi; }; \
	echo "проверка: стадия -> статус"; \
	stage "down -v (тома только лабы 5)" $(COMPOSE) down -v; \
	stage "up" $(MAKE) --no-print-directory up; \
	stage "seed (ядро)" $(MAKE) --no-print-directory seed; \
	stage "api-check" $(MAKE) --no-print-directory api-check; \
	stage "monitor-check" $(MAKE) --no-print-directory monitor-check; \
	stage "нагрузка demo (k6 verify)" $(COMPOSE) run --rm --no-deps -e MODE=verify k6; \
	echo "verify: все стадии OK"

ui:
	@open http://127.0.0.1:28080/ 2>/dev/null || xdg-open http://127.0.0.1:28080/

test:
	.venv/bin/pytest -m "not integration" -q

test-integration:
	@test -n "$(NEO4J_PASSWORD)" || { echo "нет .env — запустите make up"; exit 1; }
	NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_PASSWORD="$(NEO4J_PASSWORD)" .venv/bin/pytest -m integration -q