#!/usr/bin/env bash
# Atividade 30: medição local reproduzível, sem alegar inferência industrial.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

output="fechamento-sprint3/evidencias/atividade-30"
composition_evidence="composicao-ver1/evidencias"
if [ -e "$output/resultado.json" ] || [ -e "$composition_evidence/resultado.json" ]; then
  echo "Evidência anterior encontrada. Preserve-a e use um checkout limpo para uma nova medição." >&2
  exit 1
fi
mkdir -p "$output"
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
compose=(docker compose --project-name ver1-sprint3-local --env-file composicao-ver1/.env.example -f composicao-ver1/compose.yml)

cleanup() {
  status=$?
  trap - EXIT
  bash composicao-ver1/executar.sh parar >> "$output/encerramento.log" 2>&1 || status=1
  exit "$status"
}
trap cleanup EXIT

bash composicao-ver1/executar.sh demonstrar 2>&1 | tee "$output/composicao.log"
"${compose[@]}" run --rm --entrypoint python \
  -v "$PWD/fechamento-sprint3/medir_pipeline.py:/lab/medir_pipeline.py:ro" \
  prova /lab/medir_pipeline.py --output /evidencias/latencia.json

mapfile -t containers < <("${compose[@]}" ps -q db kafka backend frontend)
if [ "${#containers[@]}" -lt 4 ]; then
  echo "Os quatro containers medidos não estão ativos." >&2
  exit 1
fi
docker stats --no-stream --format '{{json .}}' "${containers[@]}" > "$output/docker-stats.jsonl"
"${compose[@]}" images --format json > "$output/imagens.jsonl"

{
  printf 'recorded_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'a1_commit=%s\n' "$(git rev-parse HEAD)"
  printf 'i8_commit=%s\n' "$(python3 -c 'import json; print(json.load(open("composicao-ver1/versoes.json"))["i8_commit"])')"
  printf 'runner_os=%s\n' "$(uname -a)"
  printf 'cpu_count=%s\n' "$(getconf _NPROCESSORS_ONLN)"
  printf 'memory_total_kib=%s\n' "$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  docker version --format 'docker_client={{.Client.Version}}'
  docker version --format 'docker_server={{.Server.Version}}'
  docker compose version --short | sed 's/^/docker_compose=/'
} > "$output/ambiente.txt"

cp "$composition_evidence/latencia.json" "$output/latencia.json"
python fechamento-sprint3/consolidar_metricas.py \
  --latency "$output/latencia.json" \
  --stats "$output/docker-stats.jsonl" \
  --environment "$output/ambiente.txt" \
  --images "$output/imagens.jsonl" \
  --output "$output/resultado.json"

python - "$output/resultado.json" > "$output/resumo.log" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
pipeline = value["latency"]["publisher_invocation_to_database_ms"]
api = value["latency"]["api_history_request_ms"]
print(f"status={value['status']}")
print(f"commit={value['a1_commit']}")
print(f"pipeline_samples={pipeline['samples']} p50_ms={pipeline['p50']} p95_ms={pipeline['p95_nearest_rank']} max_ms={pipeline['max']}")
print(f"api_samples={api['samples']} p50_ms={api['p50']} p95_ms={api['p95_nearest_rank']} max_ms={api['max']}")
print(f"container_memory_total_mib={value['resources']['total_memory_used_mib']}")
PY
cat "$output/resumo.log"
