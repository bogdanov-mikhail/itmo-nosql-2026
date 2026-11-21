#!/bin/sh
# One-shot подготовка стенда (запускается из образа узлов).
#
# 1. Дополняет volume os-security штатными securityconfig-файлами образа,
#    сохраняя сгенерированный certs-контейнером internal_users.yml с bcrypt-хэшами
#    паролей из .env. Кластер при ПЕРВОМ старте инициализирует из них security
#    index (allow_default_init_securityindex на os-hot).
# 2. Ждёт зелёный кластер и накладывает ролевую модель через Security REST API
#    (идемпотентно: повторные PUT только перезаписывают те же объекты).
set -eu

SEED=/seed

# --- 2. Ролевая модель через Security REST API ---
OS=https://os-hot:9200
api() {
  curl -sf --cacert "$SEED/root-ca.crt" -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
    -H 'Content-Type: application/json' "$@"
}
policy_get() {
  curl -sS --cacert "$SEED/root-ca.crt" -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" \
    -H 'Content-Type: application/json' -w '\n%{http_code}' "$@"
}
. /ism-policy.sh

# Ждём зелёный кластер (до 5 минут)
i=0
until api "$OS/_cluster/health?wait_for_status=green&timeout=5s" | grep -q '"status":"green"'; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "кластер не стал зелёным за 5 минут" >&2
    exit 1
  fi
  sleep 5
done
echo "кластер зелёный — накладываю ролевую модель"

# Своя группа записи: встроенная группа write в 3.8.0 не разворачивается в
# bulk-действия (seed-файл action_groups пуст), поэтому перечисляем явно ровно
# те действия, что нужны шипперу — полную запись без чтения и удаления.
api -XPUT "$OS/_plugins/_security/api/actiongroups/logsWrite" --data-binary @/lab-config/log-writes.json >/dev/null

# Роль записи: ТОЛЬКО data stream logs и его backing-индексы (.ds-logs-*).
# В 3.8.0 bulk-запись в стрим проверяется ДВАЖДЫ: сам запрос — как
# cluster-право (indices:data/write/bulk), а айтемы — как index-право на
# резервных индексах. Оба уровня перечислены; create_index роли не нужен:
# стрим создаёт админ.
api -XPUT "$OS/_plugins/_security/api/roles/accessLogIngest" --data-binary @/lab-config/ingest-role.json >/dev/null

# Роль чтения: чтение ТОЛЬКО индексов logs*
api -XPUT "$OS/_plugins/_security/api/roles/accessLogAnalyst" --data-binary @/lab-config/analyst-role.json >/dev/null

# Роль мониторинга: минимальные права на метрики кластера и узлов.
# indices:monitor/stats нужен плагину-экспортёру для индексных метрик
# (nested-запросы экспортёра видны в матрице доступа).
api -XPUT "$OS/_plugins/_security/api/roles/platformMonitor" --data-binary @/lab-config/monitor-role.json >/dev/null

# Маппинги: пользователи из internal_users.yml (файлы первого старта)
api -XPUT "$OS/_plugins/_security/api/rolesmapping/accessLogIngest" \
  -d '{"users": ["logshipper"]}' >/dev/null
api -XPUT "$OS/_plugins/_security/api/rolesmapping/accessLogAnalyst" \
  -d '{"users": ["analyst01"]}' >/dev/null
# analyst01 дополнительно получает доступ к интерфейсу Dashboards
api -XPUT "$OS/_plugins/_security/api/rolesmapping/kibana_user" \
  -d '{"backend_roles": ["kibanauser"], "users": ["analyst01"]}' >/dev/null
api -XPUT "$OS/_plugins/_security/api/rolesmapping/platformMonitor" \
  -d '{"users": ["metricsAgent"]}' >/dev/null

# Контроль: все три роли существуют
for r in accessLogIngest accessLogAnalyst platformMonitor; do
  api "$OS/_plugins/_security/api/roles/$r" | grep -q "$r" || {
    echo "роль $r не создалась" >&2
    exit 1
  }
done
echo "ролевая модель применена: accessLogIngest, accessLogAnalyst, platformMonitor"

# --- 3. Лог-пайплайн: интервал ISM, политика, шаблон, data stream ---

# Интервал ISM-заданий — ДО создания стрима: расписание берётся индексом при
# взятии под управление, дефолтные 5 минут превращают демо в тыкву.
api -XPUT "$OS/_cluster/settings" -d '{
  "persistent": {
    "plugins.index_state_management.job_interval": "1",
    "plugins.index_state_management.jitter": "0"
  }
}' >/dev/null
echo "ISM: job_interval=1, jitter=0"

# Политика: rollover при 1 МБ или 1 минуте (что раньше), перенос на warm
# (read_only) и удаление через 10 минут от создания индекса.
# Повторный PUT без версии даёт 409 — применяем if_seq_no/if_primary_term.
update_ism_policy
echo "ISM-политика logs-lifecycle применена"

# Шаблон индекса: явные маппинги полей лога, 1 шард / 0 реплик, только hot-узел
api -XPUT "$OS/_index_template/logs-template" --data-binary @/lab-config/log-template.json >/dev/null
echo "шаблон logs-template применён"

# Data stream создаём ДО старта шиппера: writer-роль остаётся без create_index
api "$OS/_data_stream/logs" >/dev/null 2>&1 || api -XPUT "$OS/_data_stream/logs" >/dev/null
echo "data stream logs готов"

# --- 4. Файл пароля metricsAgent для Prometheus (basic_auth password_file) ---
printf '%s' "$METRICSAGENT_PASSWORD" > "$SEED/prometheus-metricsagent.password"
echo "пароль для Prometheus выложен в seed"
