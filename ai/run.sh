#!/usr/bin/env bash
# Lance le serveur JZ-AI.
set -euo pipefail
cd "$(dirname "$0")/.."

export JZAI_ADMIN_TOKEN="${JZAI_ADMIN_TOKEN:-}"
export JZAI_BACKEND="${JZAI_BACKEND:-auto}"
export JZAI_PORT="${JZAI_PORT:-8000}"

exec python3 -m uvicorn ai.server.main:app --host "${JZAI_HOST:-0.0.0.0}" --port "$JZAI_PORT"
