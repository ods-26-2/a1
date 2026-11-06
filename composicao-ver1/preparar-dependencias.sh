#!/usr/bin/env bash
# Somente checkouts limpos, em revisões explícitas, dentro do laboratório.
set -euo pipefail
cd "$(dirname "$0")"
for repository in "$@"; do
  case "$repository" in i8|p2) ;; *) echo 'Dependência desconhecida' >&2; exit 2 ;; esac
  sha="$(python3 -c 'import json,sys; print(json.load(open("versoes.json"))[sys.argv[1]+"_commit"])' "$repository")"
  url="$(python3 -c 'import json,sys; print(json.load(open("versoes.json"))[sys.argv[1]+"_repository"])' "$repository")"
  path=".dependencias/$repository"
  if [ ! -e "$path/.git" ]; then
    mkdir -p "$path"
    git -C "$path" init -q
    git -C "$path" remote add origin "$url"
  fi
  test -z "$(git -C "$path" status --porcelain)" || { echo "Dependência $repository modificada; não será sobrescrita" >&2; exit 1; }
  if ! git -C "$path" cat-file -e "$sha^{commit}" 2>/dev/null; then
    git -C "$path" fetch --depth=1 origin "$sha"
  fi
  git -C "$path" checkout -q --detach "$sha"
  test "$(git -C "$path" rev-parse HEAD)" = "$sha"
done
