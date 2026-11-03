#!/usr/bin/env bash
# Generic validation gate. Runs every executable script in scripts/checks.d/ (sorted).
# Each check exits non-zero on failure. Refuses to pass if no checks exist, so the gate is never vacuous.
cd "$(dirname "$0")/.." || exit 1
shopt -s nullglob
checks=(scripts/checks.d/*.sh)
[ ${#checks[@]} -gt 0 ] || { echo "validate: FAILED - no checks in scripts/checks.d/ (add some, see factory-kit/checks-examples)"; exit 1; }
fail=0
for c in "${checks[@]}"; do
  [ -x "$c" ] || { echo "SKIP (not executable): $c"; continue; }
  echo "== $c"
  "$c" || { echo "FAIL: $c"; fail=1; }
done
[ $fail -eq 0 ] && echo "validate: OK" || { echo "validate: FAILED"; exit 1; }
