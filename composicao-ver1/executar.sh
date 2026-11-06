#!/usr/bin/env bash
# Composição isolada. Não usa o docker-compose.yml de implantação do A1.
set -euo pipefail
cd "$(dirname "$0")"
mode="${1:-testar}"
case "$mode" in testar|demonstrar|parar) ;; *) echo 'Uso: bash composicao-ver1/executar.sh [testar|demonstrar|parar]' >&2; exit 2 ;; esac
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
compose=(docker compose --project-name ver1-sprint3-local --env-file "${VER1_ENV_FILE:-.env.example}" -f compose.yml)
if [ "$mode" = parar ]; then
  "${compose[@]}" down -v --remove-orphans
  exit
fi
# Não apaga uma demonstração anterior nem mistura eventos de execuções diferentes.
if [ -n "$("${compose[@]}" ps -aq)" ]; then
  echo 'Laboratório já existe. Para apagar somente seus dados locais: bash composicao-ver1/executar.sh parar' >&2
  exit 1
fi
if docker volume inspect ver1-sprint3-local_lab-db >/dev/null 2>&1; then
  echo 'Volume de laboratório anterior encontrado. Execute parar antes de um novo teste.' >&2
  exit 1
fi
i8_sha="$(python3 -c 'import json; print(json.load(open("versoes.json"))["i8_commit"])')"
i8_url="$(python3 -c 'import json; print(json.load(open("versoes.json"))["i8_repository"])')"
if [ ! -d .dependencias/i8/.git ] && [ ! -f .dependencias/i8/.git ]; then
  mkdir -p .dependencias/i8
  git -C .dependencias/i8 init -q
  git -C .dependencias/i8 remote add origin "$i8_url"
  git -C .dependencias/i8 fetch --depth=1 origin "$i8_sha"
  git -C .dependencias/i8 checkout -q --detach FETCH_HEAD
fi
test "$(git -C .dependencias/i8 rev-parse HEAD)" = "$i8_sha"
test -z "$(git -C .dependencias/i8 status --porcelain)"
export VER1_A1_SHA="$(git -C .. rev-parse HEAD)"
export VER1_A1_DIRTY=false
if [ -n "$(git -C .. status --porcelain)" ]; then export VER1_A1_DIRTY=true; fi
mkdir -p evidencias
cp versoes.json evidencias/versoes.json
git -C .. diff --binary HEAD > evidencias/a1-alteracoes.patch
git -C .. status --short > evidencias/a1-estado.txt
cleanup() {
  status=$?
  trap - EXIT
  "${compose[@]}" logs --no-color --tail=200 > evidencias/containers.log 2>&1 || true
  if [ "$status" -ne 0 ] || [ "$mode" = testar ]; then
    if ! "${compose[@]}" down -v --remove-orphans > evidencias/encerramento.log 2>&1; then status=1; fi
  else
    echo 'Demonstração mantida. Use a porta VER1_PORT (padrão 5501), caminho /frontend/.'
    echo 'Ao terminar: bash composicao-ver1/executar.sh parar'
  fi
  exit "$status"
}
trap cleanup EXIT
"${compose[@]}" build backend frontend i8-publisher
"${compose[@]}" up -d --wait frontend
"${compose[@]}" run --rm prova preparar
"${compose[@]}" run --rm i8-publisher > evidencias/recibos-envio.jsonl 2> evidencias/publisher-envio.log
"${compose[@]}" run --rm prova envio
"${compose[@]}" run --rm i8-publisher > evidencias/recibos-reenvio.jsonl 2> evidencias/publisher-reenvio.log
"${compose[@]}" run --rm prova reenvio
"${compose[@]}" restart backend
"${compose[@]}" up -d --wait frontend
"${compose[@]}" run --rm prova reinicio
