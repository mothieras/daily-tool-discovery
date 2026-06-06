#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
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
[ -f "\$HOME/.hermes/.env" ] && set -a && . "\$HOME/.hermes/.env" && set +a
. "\$ROOT/.venv/bin/activate"
daily-tool-discovery discover --root "\$ROOT" --date "\$TODAY" --limit "$LIMIT" >/dev/null
cat "\$ROOT/briefings/\$TODAY.md"
SH
chmod +x "$HERMES_HOME/scripts/daily-tool-discovery.sh"

mkdir -p "$HERMES_HOME/skills/software-development"
rm -rf "$HERMES_HOME/skills/software-development/daily-tool-discovery"
cp -R "$ROOT/hermes-skills/daily-tool-discovery" "$HERMES_HOME/skills/software-development/daily-tool-discovery"

"$HERMES_HOME/scripts/daily-tool-discovery.sh" >/tmp/daily-tool-discovery-smoke.md

echo "Installed Daily Tool Discovery at $ROOT"
echo "Smoke output: /tmp/daily-tool-discovery-smoke.md"
echo "Hermes script: $HERMES_HOME/scripts/daily-tool-discovery.sh"
echo "Hermes skill: $HERMES_HOME/skills/software-development/daily-tool-discovery/SKILL.md"
