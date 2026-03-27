#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "错误：未找到项目虚拟环境 Python：$VENV_PY" >&2
  echo "请先执行：python3 -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PY" app.py "$@"
