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
2. For each approved task (run independent tasks in parallel, each worker in its own worktree if they touch the same files):
   a. Launch the `worker` agent with the task path.
   b. Launch the `validator` agent (fresh context) with the task path.
   c. On FAIL, pass the validator's fixes to a new worker round. Max 3 rounds, then stop and ask the user.
   d. On PASS, launch the `documentor` with the task path, then (after it finishes) the `runbook-refiner`
      with the task path. They edit only docs and runbooks. Give the runbook-refiner the task Log (FAILs, workarounds).
   e. Run `scripts/validate.sh` again; launch the `validator` once more to check the docs and runbook changes against
      the spec's Docs/Runbook impact. On FAIL, send fixes to the owning role (max 2 rounds, then ask the user).
   f. Only then set the task Status to `validated` and append to its Log.
3. After all tasks: launch the `runbook-refiner` for a refinement pass over every task Log of this run (recurring
   failures become troubleshooting entries; check the runbook index for gaps), and validate its changes.
4. Commit validated tasks on the current branch, one commit per task (code + docs + runbooks together).
   Summarise results to the user, including which docs and runbooks changed.
