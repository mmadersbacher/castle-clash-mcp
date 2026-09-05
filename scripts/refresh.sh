#!/usr/bin/env bash
# Full data refresh (seed + scrape). Used by the systemd timer / cron.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" -m ccmcp.refresh "$@"
