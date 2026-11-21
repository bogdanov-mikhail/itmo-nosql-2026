#!/bin/sh
# Вызывается из setup.sh; api и policy_get предоставляются вызывающим скриптом.
update_ism_policy() {
  url="$OS/_plugins/_ism/policies/logs-lifecycle"
  response=$(policy_get "$url") || {
    echo "Не удалось получить ISM-политику" >&2
    return 1
  }
  newline='
'
  status=${response##*"$newline"}
  body=${response%"$newline"*}
  case "$status" in
    200)
      versions=$(printf '%s' "$body" | jq -ers '
        if length == 1 and (.[0] | type == "object") then
          .[0] | [._seq_no, ._primary_term] |
          if all(.[]; type == "number" and . >= 0 and . == floor)
          then map(tostring) | join(" ") else error("invalid versions") end
        else error("invalid response") end
      ') || {
        echo "Некорректные версии ISM-политики" >&2
        return 1
      }
      set -- $versions
      url="$url?if_seq_no=$1&if_primary_term=$2"
      ;;
    404) ;;
    *) echo "Ошибка получения ISM-политики: HTTP $status" >&2; return 1 ;;
  esac
  api -XPUT "$url" --data-binary @"${POLICY_FILE:-/lab-config/lifecycle.json}" >/dev/null
}
