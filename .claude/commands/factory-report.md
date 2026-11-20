---
description: On request, show per-task token usage split by role, and the cross-task review of where to reduce tokens
argument-hint: [--task NNN]
---
You are the factory orchestrator handling an on-request usage report. Arguments: $ARGUMENTS

Nothing here runs on a schedule; this runs only because the user asked. It uses no model calls beyond this turn.

1. Record the current session into the ledger: `python3 scripts/factory-metrics.py record`
   (idempotent; transcripts disappear with the container, so this must happen before the session ends).
2. Show the report: `python3 scripts/factory-metrics.py report $ARGUMENTS` (add `--out factory/metrics/report.md` to keep a copy).
3. Present to the user, briefly: the per-task split by role (launches, tokens by type, share, cost if prices are filled), the
   top 3 findings from the cross-task review, and which numbered refinement each one points to.
   Say clearly if prices are missing (cost n/a) and that orchestrator figures are an attribution estimate.
4. Do NOT change the factory. Refinements are proposals; the user decides. Do not commit unless the user asks.
