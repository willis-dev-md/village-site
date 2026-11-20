---
description: On request, have the documentor update documentation (a task, a change, or a topic)
argument-hint: <task path | commit/PR | topic to document>
---
You are the factory orchestrator handling an on-request documentation job: $ARGUMENTS

Nothing here runs on a schedule; this runs only because the user asked.

1. Work out the subject: a task spec in `factory/tasks/`, a commit or branch diff, or a free-text topic. If it is unclear
   which docs are meant, ask the user one short question; otherwise proceed.
2. Launch the `documentor` agent (prompt starts with `TASK adhoc · round 1 · phase docs`) with the subject, the relevant diff or files, and the task's `Docs impact` if there is one.
   It edits documentation only (never code, never `docs/runbooks/`).
3. Run `scripts/validate.sh`; launch the `validator` agent to check that the documentation is accurate (documented commands
   actually run) and that no code changed. On FAIL, send fixes back to the documentor (max 2 rounds, then ask the user).
4. Run `python3 scripts/factory-metrics.py record`. Show the user which docs changed and anything marked UNVERIFIED. Do not commit unless the user asks.
