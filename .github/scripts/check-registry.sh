#!/usr/bin/env bash
# Verifica que experiments/registry.jsonl sólo agregue líneas respecto de un commit base
# y que no se haya recortado respecto de los resultados publicados (spec 004, US1).
#
# Uso: check-registry.sh <commit-o-rama-base>
# Falla cerrado: si no se puede obtener la base, el paso falla (no se acepta por defecto).
set -euo pipefail

REGISTRY="experiments/registry.jsonl"
BASE_REF="${1:?uso: check-registry.sh <commit-o-rama-base>}"
BASE_FILE="${RUNNER_TEMP:-/tmp}/registry-base.jsonl"

if [[ "$BASE_REF" =~ ^0+$ ]]; then
  echo "Sin commit base (rama nueva): sólo se verifica la cadena y los resultados."
  : > "$BASE_FILE"
else
  git fetch --no-tags --depth=1 origin "$BASE_REF"
  git cat-file -e FETCH_HEAD^{commit}   # error real de la base => falla
  if git cat-file -e "FETCH_HEAD:$REGISTRY" 2>/dev/null; then
    git show "FETCH_HEAD:$REGISTRY" > "$BASE_FILE"
  else
    echo "La base no tiene $REGISTRY: cualquier bitácora íntegra se acepta."
    : > "$BASE_FILE"
  fi
fi

if [[ ! -f "$REGISTRY" ]]; then
  if [[ -s "$BASE_FILE" ]]; then
    echo "error: $REGISTRY existe en la base y fue borrada." >&2
    exit 1
  fi
  echo "No hay bitácora en esta rama ni en la base."
  exit 0
fi

# TSINSURANCE_CMD permite probar el script fuera de uv (pruebas).
${TSINSURANCE_CMD:-uv run tsinsurance} experiment verify "$REGISTRY" --base "$BASE_FILE" --results experiments
