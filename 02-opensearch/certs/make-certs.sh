#!/bin/sh
# Только PKI. Неполное состояние не восстанавливается автоматически.
set -eu
umask 077
. "${PKI_STATE:-/pki-state.sh}"

if ! empty_dir "$PKI"; then
  valid_markers || fail "неполные или неверные маркеры инициализации"
  complete_pki || fail "неполная PKI; восстановите её из резервной копии"
  if [ -e "$PKI/.users-started" ] && [ ! -e "$PKI/.users-done" ]; then
    fail "создание пользователей было прервано"
  fi
  if complete_users; then
    if [ -e "$PKI/.pki-pending" ] && [ ! -e "$PKI/.users-done" ]; then
      fail "создание пользователей не завершено"
    fi
    echo "PKI и seed существуют — генерация пропущена"
    exit 0
  fi
  [ -e "$PKI/.pki-pending" ] && [ ! -e "$PKI/.users-done" ] &&
    [ ! -e "$SEC/internal_users.yml" ] && fresh_security && no_cluster_data ||
    fail "отсутствуют пользователи в существующем стенде"
  echo "PKI готова, ожидается создание пользователей"
  exit 0
fi

empty_dir "$SEC" && no_cluster_data || fail "тома security или данных не пусты"
(set -C; : > "$PKI/.pki-pending") || fail "не удалось отметить инициализацию"
command -v openssl >/dev/null 2>&1 || apk add --no-cache openssl >/dev/null
CA="$PKI/root-ca"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out "$CA.key"
openssl req -new -x509 -days 3650 -key "$CA.key" -out "$CA.crt" \
  -subj "/O=Coffee Lab/CN=Coffee Lab Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"
issue() {
  cn="$1"; shift
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$PKI/$cn.key"
  ext="/tmp/$cn.ext"
  {
    echo "basicConstraints=CA:FALSE"
    echo "keyUsage=critical,digitalSignature,keyEncipherment"
    echo "extendedKeyUsage=serverAuth,clientAuth"
    [ "$#" -eq 0 ] || printf 'subjectAltName=%s\n' "$*"
  } > "$ext"
  openssl req -new -key "$PKI/$cn.key" -subj "/O=Coffee Lab/CN=$cn" -out "/tmp/$cn.csr"
  openssl x509 -req -days 1460 -in "/tmp/$cn.csr" \
    -CA "$CA.crt" -CAkey "$CA.key" -CAcreateserial \
    -extfile "$ext" -out "$PKI/$cn.crt"
}
issue os-hot "DNS:os-hot,IP:127.0.0.1"
issue os-warm "DNS:os-warm,IP:127.0.0.1"
issue admin
issue dashboards "DNS:dashboards"
chmod 600 "$PKI"/*.key
install -m 644 "$CA.crt" "$SEC/root-ca.crt"
chown -R 1000:1000 "$PKI" "$SEC"
chmod 755 "$PKI" "$SEC"
echo "PKI создана; пользователи будут подготовлены отдельно"
