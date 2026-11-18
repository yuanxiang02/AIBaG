#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "需要 Python 3，请先安装后再运行。" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 .env。请先填入 AIBAG_API_KEY，然后重新运行 ./start.sh。"
  exit 1
fi

AIBAG_LOCAL_PORT="$(sed -n 's/^AIBAG_PORT=//p' .env | tail -n 1)"
AIBAG_LOCAL_PORT="${AIBAG_LOCAL_PORT:-8787}"
AIBAG_LOCAL_URL="http://127.0.0.1:${AIBAG_LOCAL_PORT}"

if command -v open >/dev/null 2>&1; then
  (sleep 1; open "$AIBAG_LOCAL_URL" >/dev/null 2>&1 || true) &
elif command -v xdg-open >/dev/null 2>&1; then
  (sleep 1; xdg-open "$AIBAG_LOCAL_URL" >/dev/null 2>&1 || true) &
fi

echo "AIBaG 正在启动：$AIBAG_LOCAL_URL"
exec python3 server.py
