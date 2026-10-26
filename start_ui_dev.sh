#!/usr/bin/env bash
# 开发模式：后端 8787 + Vite 5173（API 代理到后端）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install -e . >/dev/null

(cd webui && npm install)

UI_HOST="${UI_HOST:-127.0.0.1}"
UI_PORT="${UI_PORT:-8787}"
VITE_PORT="${VITE_PORT:-5173}"

python serve_ui.py --host "$UI_HOST" --port "$UI_PORT" &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> 后端 API: http://${UI_HOST}:${UI_PORT}"
echo "==> 前端开发: http://${UI_HOST}:${VITE_PORT} （Vite 代理 /api）"
(cd webui && npm run dev -- --host "$UI_HOST" --port "$VITE_PORT")
