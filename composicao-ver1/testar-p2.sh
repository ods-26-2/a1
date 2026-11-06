#!/usr/bin/env bash
# Atividades 17/18/28: prova CPU real com imagens explicitamente sintéticas.
set -euo pipefail
cd "$(dirname "$0")"
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
export VER1_PORT="${VER1_P2_PORT:-5502}"
compose=(docker compose --project-name ver1-sprint3-p2 --env-file .env.example -f compose.yml -f compose-p2.yml)
if [ -n "$("${compose[@]}" ps -aq)" ] || docker volume inspect ver1-sprint3-p2_lab-db >/dev/null 2>&1; then
  echo 'Laboratório P2 anterior encontrado; preserve evidências e encerre apenas o projeto ver1-sprint3-p2 antes de repetir.' >&2
  exit 1
fi
if [ -d evidencias-p2 ] && [ -n "$(find evidencias-p2 -mindepth 1 -print -quit)" ]; then
  echo 'evidencias-p2 já contém arquivos; arquive a pasta antes de repetir, sem sobrescrever provas.' >&2
  exit 1
fi
bash preparar-dependencias.sh i8 p2
export VER1_A1_SHA="$(git -C .. rev-parse HEAD)"
export VER1_A1_DIRTY=false
if [ -n "$(git -C .. status --porcelain)" ]; then export VER1_A1_DIRTY=true; fi
mkdir -p evidencias-p2
cp versoes.json evidencias-p2/versoes.json
git -C .. diff --binary HEAD > evidencias-p2/a1-alteracoes.patch
git -C .. status --short > evidencias-p2/a1-estado.txt
cleanup() {
  status=$?
  trap - EXIT
  "${compose[@]}" logs --no-color --tail=200 > evidencias-p2/containers.log 2>&1 || true
  if ! "${compose[@]}" down -v --remove-orphans > evidencias-p2/encerramento.log 2>&1; then status=1; fi
  exit "$status"
}
trap cleanup EXIT
docker build --build-context p2=.dependencias/p2 -f .dependencias/i8/validacao-local/Dockerfile.p2 \
  -t ver1-composicao-p2-base:local .dependencias/i8
"${compose[@]}" build backend frontend i8-publisher i8-p2
"${compose[@]}" run --rm --no-deps i8-p2 preparar > evidencias-p2/preparacao.log 2>&1
"${compose[@]}" up -d --wait frontend
if "${compose[@]}" run --rm --no-deps i8-p2 engine-ausente > evidencias-p2/engine-ausente.log 2>&1; then
  echo 'Engine ausente não interrompeu o replay' >&2; exit 1
fi
grep -q 'FileNotFoundError.*missing-engine' evidencias-p2/engine-ausente.log
test ! -e evidencias-p2/eventos.jsonl
"${compose[@]}" run --rm prova-p2 engine-ausente
"${compose[@]}" run --rm --no-deps i8-p2 inferir > evidencias-p2/recibos-envio.jsonl 2> evidencias-p2/inferencia.log
"${compose[@]}" run --rm prova-p2 envio
"${compose[@]}" run --rm i8-publisher > evidencias-p2/recibos-reenvio.jsonl 2> evidencias-p2/reenvio.log
"${compose[@]}" run --rm prova-p2 reenvio
"${compose[@]}" restart backend
"${compose[@]}" up -d --wait frontend
"${compose[@]}" run --rm prova-p2 reinicio
