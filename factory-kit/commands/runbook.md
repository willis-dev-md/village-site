---
description: On request, have the runbook-refiner create or refine runbooks (a change, an incident, or a refinement pass)
argument-hint: <task path | incident or failure description | "refine" for a pass over recent task logs>
---
You are the factory orchestrator handling an on-request runbook job: $ARGUMENTS

Nothing here runs on a schedule; this runs only because the user asked.

1. Work out the subject: a task spec (new operational behaviour), an incident or failure the user describes (include exact
   error text and what fixed it), or `refine` (a pass over the Logs of recent tasks for recurring failures and gaps in the
   runbook index). If unclear, ask the user one short question; otherwise proceed.
2. Launch the `runbook-refiner` agent (prompt starts with `TASK adhoc · round 1 · phase runbook`) with the subject, the relevant diff/Logs/incident notes. It edits `docs/runbooks/**` only.
3. Run `scripts/validate.sh`; launch the `validator` agent to check that every documented step works (it re-runs them)
   and that nothing outside `docs/runbooks/` changed. On FAIL, send fixes back to the runbook-refiner (max 2 rounds, then ask the user).
4. Run `python3 scripts/factory-metrics.py record`. Show the user which runbooks changed and anything UNVERIFIED. Do not commit unless the user asks.
