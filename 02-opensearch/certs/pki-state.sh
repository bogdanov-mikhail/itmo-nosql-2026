#!/bin/sh
PKI=/certs/pki
SEC=/certs/security
HOT=${PKI_DATA_HOT:-/data/hot}
WARM=${PKI_DATA_WARM:-/data/warm}

fail() { echo "Ошибка PKI/seed: $*" >&2; exit 1; }
empty_dir() {
  [ -d "$1" ] && [ -z "$(find "$1" -mindepth 1 -print -quit)" ]
}
no_cluster_data() {
  empty_dir "$HOT" && empty_dir "$WARM"
}
fresh_security() {
  [ -d "$SEC" ] &&
    [ -z "$(find "$SEC" -mindepth 1 -maxdepth 1 ! -name root-ca.crt -print -quit)" ]
}
valid_markers() {
  for marker in .pki-pending .users-started .users-done; do
    [ ! -L "$PKI/$marker" ] || return 1
    [ ! -e "$PKI/$marker" ] || [ -f "$PKI/$marker" ] || return 1
  done
  if [ -e "$PKI/.users-started" ] || [ -e "$PKI/.users-done" ]; then
    [ -e "$PKI/.pki-pending" ] && [ -e "$PKI/.users-started" ] &&
      [ -e "$PKI/.users-done" ] || return 1
  fi
}
complete_pki() {
  for file in root-ca.crt root-ca.key os-hot.crt os-hot.key os-warm.crt \
      os-warm.key admin.crt admin.key dashboards.crt dashboards.key; do
    [ -s "$PKI/$file" ] && [ ! -L "$PKI/$file" ] || return 1
  done
  [ -s "$SEC/root-ca.crt" ] && [ ! -L "$SEC/root-ca.crt" ] &&
    cmp -s "$PKI/root-ca.crt" "$SEC/root-ca.crt"
}
complete_users() {
  users="$SEC/internal_users.yml"
  [ -s "$users" ] && [ ! -L "$users" ] || return 1
  python3 - "$users" <<'PY'
import re
import sys

expected = {"admin", "kibanaserver", "logshipper", "analyst01", "metricsAgent"}
seen = {}
current = None
try:
    for line in open(sys.argv[1], encoding="utf-8"):
        header = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*", line)
        if header:
            current = header.group(1)
            if current in expected:
                if current in seen:
                    raise ValueError("duplicate user")
                seen[current] = 0
        elif re.match(r"\s+hash:", line):
            if current not in expected or not re.fullmatch(
                r'\s+hash:\s*"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}"\s*', line
            ):
                raise ValueError("invalid hash")
            seen[current] += 1
    if set(seen) != expected or any(count != 1 for count in seen.values()):
        raise ValueError("incomplete users")
except (OSError, UnicodeError, ValueError):
    sys.exit(1)
PY
}
