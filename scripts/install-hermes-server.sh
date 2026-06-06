#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HERMES_BIN="${HERMES_BIN:-hermes}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LIMIT="${LIMIT:-40}"
SCHEDULE="${SCHEDULE:-0 9 * * *}"
DELIVER="${DELIVER:-local}"
INSTALL_CRON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cron)
      INSTALL_CRON=1
      shift
      ;;
    --deliver)
      DELIVER="$2"
      shift 2
      ;;
    --schedule)
      SCHEDULE="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"
"$PYTHON_BIN" -m venv .venv
. "$ROOT/.venv/bin/activate"
python -m pip install -U pip
python -m pip install -e .

mkdir -p "$HERMES_HOME/scripts"
cat > "$HERMES_HOME/scripts/daily-tool-discovery.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail

ROOT="$ROOT"
TODAY="\$(date +%F)"

cd "\$ROOT"
. "\$ROOT/.venv/bin/activate"
daily-tool-discovery discover --root "\$ROOT" --date "\$TODAY" --limit "$LIMIT" >/dev/null
cat "\$ROOT/briefings/\$TODAY.md"
SH
chmod +x "$HERMES_HOME/scripts/daily-tool-discovery.sh"

"$HERMES_HOME/scripts/daily-tool-discovery.sh" >/tmp/daily-tool-discovery-smoke.md

if [[ "$INSTALL_CRON" -eq 1 ]]; then
  "$HERMES_BIN" cron create "$SCHEDULE" \
    --name daily-tool-discovery \
    --script daily-tool-discovery.sh \
    --no-agent \
    --deliver "$DELIVER"
fi

echo "Installed Daily Tool Discovery at $ROOT"
echo "Smoke output: /tmp/daily-tool-discovery-smoke.md"
echo "Hermes script: $HERMES_HOME/scripts/daily-tool-discovery.sh"
