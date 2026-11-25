#!/usr/bin/env bash
# Generates local-only secrets under secrets/. Never overwrites, never prints values.
# Canonical files: secrets/<name>. Optional operator overrides: secrets/<name>.local
set -euo pipefail
umask 077

command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="$root/secrets"
mkdir -p "$dir"
chmod 0700 "$dir"

generate() {
  local name="$1" file="$dir/$1"
  if [[ -e "$file" ]]; then
    echo "kept     $name (already exists)"
  else
    openssl rand -hex 32 | tr -d '\n' > "$file"
    echo "created  $name"
  fi
  chmod 0600 "$file"
}

generate postgres_password
generate jwt_secret

echo
ls -l "$dir"
