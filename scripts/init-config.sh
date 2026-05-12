#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

copy_if_missing() {
  local src="$1"
  local dest="$2"

  if [[ -f "${dest}" ]]; then
    echo "[SKIP] ${dest} already exists"
    return
  fi

  cp "${src}" "${dest}"
  echo "[OK] created ${dest}"
}

copy_if_missing "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
copy_if_missing "${ROOT_DIR}/config/sources.example.yaml" "${ROOT_DIR}/config/sources.yaml"
copy_if_missing "${ROOT_DIR}/config/pipeline.example.yaml" "${ROOT_DIR}/config/pipeline.yaml"
