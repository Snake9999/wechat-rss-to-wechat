#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[INFO] bootstrap project at ${ROOT_DIR}"
"${ROOT_DIR}/scripts/init-config.sh"
"${ROOT_DIR}/scripts/install.sh"
"${ROOT_DIR}/scripts/doctor.sh"
