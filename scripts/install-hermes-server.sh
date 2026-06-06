#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HERMES_BIN="${HERMES_BIN:-hermes}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LIMIT="${LIMIT:-80}"
SCHEDULE="${SCHEDULE:-0 9 * * *}"
DELIVER="${DELIVER:-local}"
INSTALL_CRON=0
INSTALL_AGENT_CRON=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cron)
      INSTALL_CRON=1
      shift
      ;;
    --agent-cron)
      INSTALL_AGENT_CRON=1
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

if [[ "$INSTALL_CRON" -eq 1 && "$INSTALL_AGENT_CRON" -eq 1 ]]; then
  echo "Use either --cron or --agent-cron, not both." >&2
  exit 2
fi

cd "$ROOT"
"$PYTHON_BIN" -m venv .venv
. "$ROOT/.venv/bin/activate"
python -m pip install -U pip
python -m pip install -e .

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Warning: GITHUB_TOKEN is not set. GitHub metadata may hit low unauthenticated rate limits." >&2
fi

mkdir -p "$ROOT/seeds"
if [[ ! -f "$ROOT/seeds/manual.jsonl" && -f "$ROOT/seeds/manual.example.jsonl" ]]; then
  cp "$ROOT/seeds/manual.example.jsonl" "$ROOT/seeds/manual.jsonl"
fi

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

mkdir -p "$HERMES_HOME/skills/software-development"
rm -rf "$HERMES_HOME/skills/software-development/daily-tool-discovery"
cp -R "$ROOT/hermes-skills/daily-tool-discovery" "$HERMES_HOME/skills/software-development/daily-tool-discovery"

"$HERMES_HOME/scripts/daily-tool-discovery.sh" >/tmp/daily-tool-discovery-smoke.md

if [[ "$INSTALL_CRON" -eq 1 ]]; then
  "$HERMES_BIN" cron create "$SCHEDULE" \
    --name daily-tool-discovery \
    --script daily-tool-discovery.sh \
    --no-agent \
    --deliver "$DELIVER"
fi

if [[ "$INSTALL_AGENT_CRON" -eq 1 ]]; then
  "$HERMES_BIN" cron create "$SCHEDULE" \
    "Review today's Daily Tool Discovery briefing. Pick at most one try item and up to two save items. Use the daily-tool-discovery skill and do not discover or install anything." \
    --name daily-tool-discovery-agent \
    --script daily-tool-discovery.sh \
    --skill daily-tool-discovery \
    --deliver "$DELIVER"
fi

echo "Installed Daily Tool Discovery at $ROOT"
echo "Smoke output: /tmp/daily-tool-discovery-smoke.md"
echo "Hermes script: $HERMES_HOME/scripts/daily-tool-discovery.sh"
echo "Hermes skill: $HERMES_HOME/skills/software-development/daily-tool-discovery/SKILL.md"
