#!/usr/bin/env bash
# Usage: factory-kit/install.sh [target-dir] [--check <example>]   e.g. --check node
# Installs the factory (worker, validator, documentor, runbook-refiner) into a project. Safe to re-run:
# kit files are refreshed; your checks, tasks and runbooks are kept. An agent file containing the line
# "<!-- factory-kit: customized -->" is project-owned and is not overwritten (diff it against the kit by hand).
set -euo pipefail
kit="$(cd "$(dirname "$0")" && pwd)"
target="${1:-.}"; check=""
[ "${2:-}" = "--check" ] && check="${3:?--check needs an example name}"
mkdir -p "$target/.claude/agents" "$target/.claude/commands" "$target/factory/tasks" "$target/scripts/checks.d" "$target/docs/runbooks"
for f in "$kit"/agents/*.md; do
  dest="$target/.claude/agents/$(basename "$f")"
  if [ -f "$dest" ] && grep -q "factory-kit: customized" "$dest"; then echo "kept customized agent: $dest"; else cp "$f" "$dest"; fi
done
cp "$kit"/commands/*.md "$target/.claude/commands/"
if [ -f "$target/factory/tasks/_template.md" ] && grep -q "factory-kit: customized" "$target/factory/tasks/_template.md"; then echo "kept customized task template"; else cp "$kit/tasks/_template.md" "$target/factory/tasks/_template.md"; fi
cp "$kit/scripts/validate.sh" "$target/scripts/validate.sh"; chmod +x "$target/scripts/validate.sh"
cp "$kit/scripts/factory-roles-check.sh" "$target/scripts/checks.d/00-factory-roles.sh"; chmod +x "$target/scripts/checks.d/00-factory-roles.sh"
mkdir -p "$target/factory/metrics"
cp "$kit/scripts/factory-metrics.py" "$target/scripts/factory-metrics.py"; chmod +x "$target/scripts/factory-metrics.py"
cp "$kit/metrics/README.md" "$target/factory/metrics/README.md"
[ -f "$target/factory/metrics/prices.json" ] || cp "$kit/metrics/prices.json" "$target/factory/metrics/prices.json"
cp "$kit/runbooks/_template.md" "$target/docs/runbooks/_template.md"
[ -f "$target/docs/runbooks/README.md" ] || cp "$kit/runbooks/README.md" "$target/docs/runbooks/README.md"
if [ -n "$check" ]; then
  cp "$kit/checks-examples/$check.sh" "$target/scripts/checks.d/10-$check.sh"; chmod +x "$target/scripts/checks.d/10-$check.sh"
fi
# CLAUDE.md: add the factory section, or replace an existing one (up to the next "## " heading or end of file).
claude="$target/CLAUDE.md"
if grep -q "^## Software factory" "$claude" 2>/dev/null; then
  python3 - "$claude" "$kit/CLAUDE.factory.md" <<'PY'
import re, sys
p, k = sys.argv[1], sys.argv[2]
s, new = open(p, encoding="utf-8").read(), open(k, encoding="utf-8").read().rstrip() + "\n"
m = re.search(r"^## Software factory.*?(?=^## |\Z)", s, re.S | re.M)
open(p, "w", encoding="utf-8").write(s[:m.start()] + new + ("\n" + s[m.end():] if s[m.end():].strip() else ""))
PY
else
  { [ -f "$claude" ] && echo; cat "$kit/CLAUDE.factory.md"; } >> "$claude"
fi
echo "Installed factory into $target. Add/adjust checks in scripts/checks.d/, then run /factory <goal>."
