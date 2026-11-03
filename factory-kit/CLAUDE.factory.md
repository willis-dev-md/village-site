## Software factory

Work is produced by a factory: an **orchestrator** (the main session) splits work into tasks,
**workers** implement them, **validators** independently check them.

- Workers never validate their own work; validators never edit code.
- A task is done only when `scripts/validate.sh` passes AND the validator agent returns `PASS`.
- Max 3 worker→validator rounds per task, then escalate to the user.
- Task specs live in `factory/tasks/NNN-slug.md` (copy `factory/tasks/_template.md`).
- Project checks are scripts in `scripts/checks.d/`; add one per quality gate (tests, lint, a11y, ...).
- Run the loop with `/factory <goal>`.
