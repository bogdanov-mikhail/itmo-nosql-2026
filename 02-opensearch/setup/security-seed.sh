#!/bin/sh
set -eu
src=/usr/share/opensearch/config/opensearch-security
seed=/seed
test -f "$seed/internal_users.yml"
for file in "$src"/*.yml; do
  name=${file##*/}
  [ "$name" = internal_users.yml ] || cp "$file" "$seed/$name"
done
