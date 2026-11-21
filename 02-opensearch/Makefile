# Единый вход стенда ЛР-2 (OpenSearch на Docker Compose).
# Секреты — в .env рядом с docker-compose.yml (см. .env.example).

COMPOSE = docker compose

.DEFAULT_GOAL := help
.PHONY: help up down status rbac-matrix pipeline-check monitor-check load pipeline-cycle

help: ## список целей
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

up: ## поднять весь стенд (certs/setup отрабатывают внутри)
	$(COMPOSE) up -d

down: ## остановить и удалить контейнеры (данные в томах остаются)
	$(COMPOSE) down

status: ## состояние контейнеров
	$(COMPOSE) ps

rbac-matrix: ## матрица доступа реальными запросами (после полного up)
	$(COMPOSE) run --rm checks checks.rbac

pipeline-check: ## живая проверка лог-пайплайна (страница -> логи -> стрим)
	$(COMPOSE) run --rm checks checks.pipeline

monitor-check: ## проверка цепочки экспортёр -> Prometheus -> Grafana
	$(COMPOSE) run --rm checks checks.monitor

load: ## нагрузка k6 на страницу (разгон + устойчивая фаза, ~3.5 мин)
	$(COMPOSE) run --rm --no-deps k6

pipeline-cycle: ## полный живой цикл ISM (rollover -> warm -> delete, ~12 мин)
	$(COMPOSE) run --rm checks checks.cycle

verify: ## проверка работающего стенда без удаления данных
	$(COMPOSE) up -d --wait --wait-timeout 300
	$(COMPOSE) run --rm checks checks.rbac
	$(COMPOSE) run --rm checks checks.pipeline
	$(COMPOSE) run --rm checks checks.monitor
