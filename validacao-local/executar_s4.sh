#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
mkdir -p validacao-local/evidencias-s4
compose=(docker compose -p ver1-s4-kafka -f validacao-local/compose-s4-kafka.yml)
cleanup() {
  code=$?
  trap - EXIT
  if (( code != 0 )); then "${compose[@]}" logs --tail=120 > validacao-local/evidencias-s4/diagnostico.log 2>&1 || true; fi
  "${compose[@]}" down -v || code=1
  exit "$code"
}
trap cleanup EXIT
"${compose[@]}" up -d --build --wait backend s4-fake
"${compose[@]}" run --rm proof
"${compose[@]}" restart backend
"${compose[@]}" up -d --wait backend
"${compose[@]}" run --rm proof --recheck
