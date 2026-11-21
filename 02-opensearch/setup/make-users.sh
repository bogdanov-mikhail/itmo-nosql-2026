#!/bin/sh
# Начальные bcrypt-пользователи. Существующие пароли не изменяются.
set -eu
umask 077
. "${PKI_STATE:-/pki-state.sh}"
valid_markers || fail "неполные или неверные маркеры инициализации"
complete_pki || fail "неполная PKI"
if complete_users; then
  if [ -e "$PKI/.pki-pending" ] && [ ! -e "$PKI/.users-done" ]; then
    fail "незавершённое создание пользователей; восстановите seed"
  fi
  echo "Начальные пользователи существуют — генерация пропущена"
  exit 0
fi
[ ! -e "$SEC/internal_users.yml" ] || fail "неполный seed пользователей"
[ -e "$PKI/.pki-pending" ] && [ ! -e "$PKI/.users-started" ] &&
  [ ! -e "$PKI/.users-done" ] && fresh_security && no_cluster_data ||
  fail "неоднозначное состояние seed или данные кластера уже существуют"
for key in OPENSEARCH_INITIAL_ADMIN_PASSWORD KIBANASERVER_PASSWORD LOGSHIPPER_PASSWORD ANALYST_PASSWORD METRICSAGENT_PASSWORD; do
  eval 'value=${'"$key"':-}'
  [ -n "$value" ] || fail "не задан пароль $key"
done
(set -C; : > "$PKI/.users-started") || fail "не удалось отметить создание пользователей"
python3 -c 'import bcrypt' 2>/dev/null || pip install --quiet bcrypt
python3 - <<'PY'
import bcrypt
import os

users = [
    ("admin", "OPENSEARCH_INITIAL_ADMIN_PASSWORD", '  reserved: true\n  backend_roles:\n    - "admin"\n', "Администратор стенда"),
    ("kibanaserver", "KIBANASERVER_PASSWORD", "  reserved: true\n", "Служебный пользователь Dashboards"),
    ("logshipper", "LOGSHIPPER_PASSWORD", "", "Отправка логов nginx (Fluent Bit)"),
    ("analyst01", "ANALYST_PASSWORD", "", "Аналитик: чтение логов в Dashboards"),
    ("metricsAgent", "METRICSAGENT_PASSWORD", "", "Сбор метрик Prometheus"),
]
fd = os.open("/certs/security/internal_users.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    output.write('_meta:\n  type: "internalusers"\n  config_version: 2\n')
    for name, variable, extra, description in users:
        value = bcrypt.hashpw(os.environ[variable].encode(), bcrypt.gensalt(rounds=12, prefix=b"2a")).decode()
        output.write(f'{name}:\n  hash: "{value}"\n{extra}  description: "{description}"\n')
PY
complete_users || fail "сгенерирован неполный seed"
chown 1000:1000 "$SEC/internal_users.yml"
(set -C; : > "$PKI/.users-done") || fail "не удалось завершить инициализацию"
chown 1000:1000 "$PKI/.users-started" "$PKI/.users-done"
echo "Начальные пользователи созданы"
