#!/usr/bin/env bash
# Usage: factory-kit/install.sh [target-dir] [--check <example>]   e.g. --check node
# Installs the factory into a project. Safe to re-run: kit files are refreshed, your checks/tasks/CLAUDE.md are kept.
set -euo pipefail
kit="$(cd "$(dirname "$0")" && pwd)"
target="${1:-.}"; check=""
[ "${2:-}" = "--check" ] && check="${3:?--check needs an example name}"
mkdir -p "$target/.claude/agents" "$target/.claude/commands" "$target/factory/tasks" "$target/scripts/checks.d"
cp "$kit"/agents/*.md "$target/.claude/agents/"
cp "$kit"/commands/*.md "$target/.claude/commands/"
cp "$kit/tasks/_template.md" "$target/factory/tasks/_template.md"
cp "$kit/scripts/validate.sh" "$target/scripts/validate.sh"; chmod +x "$target/scripts/validate.sh"
if [ -n "$check" ]; then
  cp "$kit/checks-examples/$check.sh" "$target/scripts/checks.d/10-$check.sh"; chmod +x "$target/scripts/checks.d/10-$check.sh"
fi
if ! grep -q "^## Software factory" "$target/CLAUDE.md" 2>/dev/null; then
  { [ -f "$target/CLAUDE.md" ] && echo; cat "$kit/CLAUDE.factory.md"; } >> "$target/CLAUDE.md"
fi
echo "Installed factory into $target. Add/adjust checks in scripts/checks.d/ then run /factory <goal>."
