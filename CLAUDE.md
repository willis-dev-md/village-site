# The Village

Static site (no build step). See README.md.

## Communication with the user
- Keep messages short: about half the usual length.
- Message the user only for: a decision they must make; a finished spike or task (one short summary: result, next step); a blocker or anything risky or irreversible.
- No progress narration, no restating what agents or hooks said, no "waiting" updates. Give a one-line status only when asked.
- Put detail in files (task Log, docs, reports) and link to it instead of pasting it.
- Hook reminders (e.g. about uncommitted changes): reply in one line, or not at all.

## Software factory

Work is produced by a factory: an **orchestrator** (the main session) splits work into tasks and four roles do it:
a **worker** implements, a **validator** independently checks, a **documentor** keeps the documentation true, and a
**runbook-refiner** (support) keeps runbooks and troubleshooting guides true. The four roles are mandatory in every factory.

- Workers never validate their own work; validators never edit code; documentor and runbook-refiner never edit code.
- A task is done only when `scripts/validate.sh` passes, the validator returns `PASS`, AND the documentor and
  runbook-refiner have run (docs and runbooks updated, or an explicit `none: <reason>` in the spec, which the validator checks).
- Max 3 worker→validator rounds per task, then escalate to the user.
- Task specs live in `factory/tasks/NNN-slug.md` (copy `factory/tasks/_template.md`); each has `Docs impact` and `Runbook impact`.
- Runbooks live in `docs/runbooks/` (index in `docs/runbooks/README.md`, template in `_template.md`); only commands that were run are documented.
- Project checks are scripts in `scripts/checks.d/`; add one per quality gate (tests, lint, a11y, ...).
  `00-factory-roles.sh` enforces the roles and the impact sections and is installed by the kit: do not remove it.
- Run the loop with `/factory <goal>`.
- Usage metrics: every agent prompt starts with `TASK <NNN> · round <R> · phase <...>`; `scripts/factory-metrics.py record` keeps the ledger
  `factory/metrics/usage.jsonl` (no model cost, deduplicated per request); `/factory-report` shows the per-task split by role and the
  cross-task review, on request only. The report proposes refinements; the user decides what changes in the factory.
- The documentor and runbook-refiner also run **on request, never on a schedule**: `/document <task|change|topic>` and
  `/runbook <task|incident|refine>`. Do not create scheduled or background jobs for them.
