#!/usr/bin/env bash
# Atividade 29: regressão consolidada da composição local VER-1.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

output="fechamento-sprint3/evidencias/atividade-29"
database_evidence="validacao-local/evidencias-s5-p7"
composition_evidence="composicao-ver1/evidencias"
project="ver1-sprint3-regressao"

if [ -e "$output/resultado.json" ] || [ -e "$composition_evidence/resultado.json" ]; then
  echo "Evidência anterior encontrada. Preserve-a e use um checkout limpo para uma nova execução." >&2
  exit 1
fi

mkdir -p "$output" "$database_evidence"
printf '%s\n' \
  'python scripts/validate_contracts.py' \
  'python -m pytest -q --junitxml=/evidencias/regressao.xml' \
  'npm test' \
  'bash composicao-ver1/executar.sh testar' \
  > "$output/comandos.txt"

{
  printf 'recorded_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'a1_commit=%s\n' "$(git rev-parse HEAD)"
  printf 'a1_tree_clean=%s\n' "$(test -z "$(git status --porcelain)" && echo true || echo false)"
  printf 'runner_os=%s\n' "$(uname -a)"
  docker version --format 'docker_client={{.Client.Version}} docker_server={{.Server.Version}}'
  docker compose version
} > "$output/ambiente.txt"

cleanup() {
  status=$?
  trap - EXIT
  docker compose -p "$project" -f validacao-local/compose-s5-p7.yml down -v --remove-orphans \
    >> "$output/encerramento.log" 2>&1 || status=1
  bash composicao-ver1/executar.sh parar >> "$output/encerramento.log" 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

set -o pipefail
docker compose -p "$project" -f validacao-local/compose-s5-p7.yml run --rm --build testes \
  sh -c 'python scripts/validate_contracts.py && python -m pytest -q --junitxml=/evidencias/regressao.xml && npm test' \
  2>&1 | tee "$output/regressao.log"

cp "$database_evidence/regressao.xml" "$output/regressao.xml"
docker compose -p "$project" -f validacao-local/compose-s5-p7.yml down -v --remove-orphans \
  >> "$output/encerramento.log" 2>&1

bash composicao-ver1/executar.sh testar 2>&1 | tee "$output/composicao.log"
cp "$composition_evidence/resultado.json" "$output/composicao-resultado.json"
cp "$composition_evidence/versoes.json" "$output/composicao-versoes.json"
cp "$composition_evidence/a1-estado.txt" "$output/composicao-a1-estado.txt"

python fechamento-sprint3/consolidar_regressao.py \
  --junit "$output/regressao.xml" \
  --composition "$output/composicao-resultado.json" \
  --environment "$output/ambiente.txt" \
  --output "$output/resultado.json"

python - "$output/resultado.json" > "$output/resumo.log" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
tests = value["gates"]["python_tests"]
print(f"status={value['status']}")
print(f"commit={value['a1_commit']}")
print(f"python_tests={tests['passed']} passed; {tests['skipped']} skipped; {tests['failures']} failures; {tests['errors']} errors")
print(f"frontend_tests={value['gates']['frontend']['status']}")
print(f"contracts={value['gates']['contracts']['status']}")
print(f"database={value['gates']['database']['status']}")
print(f"kafka={value['gates']['kafka']['status']}")
print(f"restart={value['gates']['restart']['status']}")
PY

cat "$output/resumo.log"
