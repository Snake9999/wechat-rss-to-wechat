#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ACTION="${1:-run}"
shift || true

case "${ACTION}" in
  prepare)
    "${ROOT_DIR}/skill/scripts/prepare.sh" "$@"
    ;;
  bootstrap)
    "${ROOT_DIR}/skill/scripts/bootstrap.sh" "$@"
    ;;
  doctor)
    "${ROOT_DIR}/skill/scripts/doctor.sh" "$@"
    ;;
  sync)
    cd "${ROOT_DIR}"
    python3 -m app.main sync-sources "$@"
    ;;
  candidates)
    "${ROOT_DIR}/scripts/daily-candidates.sh" "$@"
    ;;
  run)
    "${ROOT_DIR}/scripts/run-once.sh" "$@"
    ;;
  *)
    echo "[FAIL] unknown action: ${ACTION}"
    echo "Usage: ./run_pipeline.sh [prepare|bootstrap|doctor|sync|candidates|run] [args...]"
    exit 1
    ;;
esac
