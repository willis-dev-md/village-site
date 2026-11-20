#!/usr/bin/env bash
# Factory roles gate. Installed as scripts/checks.d/00-factory-roles.sh. Fails when the factory is missing a role
# or a task skipped its documentation / runbook impact. Roles are mandatory in every factory.
cd "$(dirname "$0")/../.." || exit 1
fail=0
err() { echo "FAIL: $*"; fail=1; }

for a in worker validator documentor runbook-refiner; do
  f=".claude/agents/$a.md"
  [ -f "$f" ] || { err "missing agent $f (every factory needs worker, validator, documentor, runbook-refiner)"; continue; }
  grep -q "^name: $a\$" "$f" || err "$f: frontmatter 'name: $a' missing"
done
for w in documentor runbook-refiner; do
  grep -q "$w" .claude/commands/factory.md 2>/dev/null || err ".claude/commands/factory.md no longer runs the $w"
  grep -qi "$w" CLAUDE.md 2>/dev/null || err "CLAUDE.md does not describe the $w role"
done
for c in document runbook factory-report; do [ -f ".claude/commands/$c.md" ] || err "missing on-request command .claude/commands/$c.md"; done
[ -f scripts/factory-metrics.py ] || err "missing scripts/factory-metrics.py (usage ledger)"
[ -f factory/metrics/README.md ] && [ -f factory/metrics/prices.json ] || err "missing factory/metrics/README.md or prices.json"
if [ -f scripts/factory-metrics.py ]; then python3 -I scripts/factory-metrics.py selftest >/dev/null 2>&1 || err "factory-metrics selftest failed (run: python3 -I scripts/factory-metrics.py selftest)"; fi
[ -f docs/runbooks/README.md ] || err "docs/runbooks/README.md missing (runbook index)"
[ -f docs/runbooks/_template.md ] || err "docs/runbooks/_template.md missing"

python3 -I - <<'PY' || fail=1
import glob, re, sys
bad = 0
def section(text, name):
    m = re.search(r"^## " + re.escape(name) + r"\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None
for f in sorted(glob.glob("factory/tasks/[0-9]*.md")):
    t = open(f, encoding="utf-8").read()
    status = (section(t, "Status") or "").split("\n")[0].strip().lower()
    for name in ("Docs impact", "Runbook impact"):
        s = section(t, name)
        if s is None: print(f"FAIL: {f}: missing '## {name}' section"); bad = 1; continue
        low = s.lower()
        if not s or low.startswith(("tbd", "todo", "<", "what ", "docs that", "runbooks that")) :
            print(f"FAIL: {f}: '{name}' is empty or still the template text"); bad = 1
        elif low.startswith("none") and not re.match(r"none\s*[:\-–]\s*\S.{9,}", s, re.I | re.S):
            print(f"FAIL: {f}: '{name}' says none without a reason (write 'none: <why>')"); bad = 1
sys.exit(bad)
PY
[ $fail -eq 0 ] && echo "factory roles: OK"
exit $fail
