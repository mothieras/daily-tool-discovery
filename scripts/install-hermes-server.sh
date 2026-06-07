#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DIR="$HERMES_HOME/skills/software-development/daily-tool-discovery"
DATA_ROOT="${DAILY_TOOL_DISCOVERY_HOME:-$HOME/.daily-tool-discovery}"
LIMIT="${LIMIT:-80}"

while [[ $# -gt 0 ]]; do
  case "$1" in
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

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Warning: GITHUB_TOKEN is not set. GitHub metadata may hit low unauthenticated rate limits." >&2
fi

# Drop the self-contained skill folder into the Hermes skills dir (stdlib-only; no venv/pip).
rm -rf "$SKILL_DIR"
mkdir -p "$(dirname "$SKILL_DIR")"
cp -r "$ROOT/daily-tool-discovery" "$SKILL_DIR"

# Create the data root and seed it by running the skill once (dry-run needs no token;
# it also triggers ensure_data_root to copy the example profile + seed into the data root).
mkdir -p "$DATA_ROOT"
DAILY_TOOL_DISCOVERY_HOME="$DATA_ROOT" python3 "$SKILL_DIR/scripts/run.py" dry-run >/tmp/daily-tool-discovery-smoke.md 2>&1 || true

# Thin cron wrapper.
mkdir -p "$HERMES_HOME/scripts"
cat > "$HERMES_HOME/scripts/daily-tool-discovery.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="$DATA_ROOT"
SKILL_DIR="$SKILL_DIR"
TODAY="\$(date +%F)"

[ -f "\$HOME/.hermes/.env" ] && set -a && . "\$HOME/.hermes/.env" && set +a
DAILY_TOOL_DISCOVERY_HOME="\$DATA_ROOT" python3 "\$SKILL_DIR/scripts/run.py" discover --limit $LIMIT >/dev/null
cat "\$DATA_ROOT/briefings/\$TODAY.md"
SH
chmod +x "$HERMES_HOME/scripts/daily-tool-discovery.sh"

echo "Installed Daily Tool Discovery skill at $SKILL_DIR"
echo "Data root: $DATA_ROOT"
echo "Smoke output: /tmp/daily-tool-discovery-smoke.md"
echo "Hermes script: $HERMES_HOME/scripts/daily-tool-discovery.sh"
echo "Hermes skill: $SKILL_DIR/SKILL.md"
