---
description: Run the software factory loop on a goal
argument-hint: <goal>
---
You are the factory orchestrator. Goal: $ARGUMENTS

Roles: `worker` implements, `validator` independently checks, `documentor` keeps docs true, `runbook-refiner`
keeps runbooks/support guides true. All four are mandatory for every task; never skip one.

1. Break the goal into small, independent tasks. Write each to `factory/tasks/NNN-slug.md` from `_template.md`
   with checkable acceptance criteria **and** a `Docs impact` and `Runbook impact` (each a real list or
   `none: <reason>`). Show the list to the user and wait for approval.
Metrics: start **every** agent prompt with a tag line `TASK <NNN> · round <R> · phase <code|validate|docs|runbook|docs-check>`
(then the instructions). This is how token usage is split per task and role; it costs nothing.

2. For each approved task (run independent tasks in parallel, each worker in its own worktree if they touch the same files):
   a. Launch the `worker` agent with the task path.
   b. Launch the `validator` agent (fresh context, phase `validate`) with the task path. It is also the only reviewer of any
      `none: <reason>` in Docs impact / Runbook impact; an unjustified reason is a FAIL.
   c. On FAIL, pass the validator's fixes to a new worker round. Max 3 rounds, then stop and ask the user.
   d. On PASS: run `python3 scripts/factory-docs-check.py snapshot NNN`. Then launch the `documentor` unless Docs impact is
      `none: <reason>`, and (after it finishes) the `runbook-refiner` unless Runbook impact is `none: <reason>`. A skipped role
      gets a Log line (`documentor skipped: none: <reason>`). They edit only docs and runbooks; give the runbook-refiner the
      task Log (FAILs, workarounds). They tag command blocks they ran with `<!-- verify -->` (see their agent files).
   e. Run `python3 scripts/factory-docs-check.py check NNN` and `scripts/validate.sh` (deterministic, no agent). This replaces the
      second validator pass. On FAIL, append a Log line (`docs-check FAIL: <reason>`) and send the listed fixes to the owning role (max 2 rounds, then ask the user);
      the documentor and runbook-refiner run on a smaller model by default, so run the FIRST fix round with the strong model (pass `model: sonnet` on that Agent call). On WARN, read the
      warning yourself; only if you cannot resolve it, escalate by launching the `validator` (phase `docs-check`) on the docs.
   f. Only then set the task Status to `validated` and append to its Log. Then run `python3 scripts/factory-metrics.py record`
      (no model cost) so the usage ledger is updated and committed with the task.
3. After all tasks: launch the `runbook-refiner` for a refinement pass over every task Log of this run (recurring
   failures become troubleshooting entries; check the runbook index for gaps), and validate its changes.
4. Run `python3 scripts/factory-metrics.py record` once more. Commit validated tasks on the current branch, one commit per task (code + docs + runbooks + `factory/metrics/usage.jsonl` together).
   Summarise results to the user, including which docs and runbooks changed.
