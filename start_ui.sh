#!/usr/bin/env bash
# 启动 Web 操作台（生产模式：Python 托管 webui/dist）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> 创建虚拟环境: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  pip install -e . >/dev/null
fi

if [[ ! -d webui/dist ]]; then
  echo "==> 构建前端 (webui/dist)..."
  (cd webui && npm install && npm run build)
fi

HOST="${UI_HOST:-127.0.0.1}"
PORT="${UI_PORT:-8787}"
echo "==> Web 操作台: http://${HOST}:${PORT}"
exec python serve_ui.py --host "$HOST" --port "$PORT"
