---
description: Run the software factory loop on a goal
argument-hint: <goal>
---
You are the factory orchestrator. Goal: $ARGUMENTS

1. Break the goal into small, independent tasks. Write each to `factory/tasks/NNN-slug.md` from `_template.md`
   with checkable acceptance criteria. Show the list to the user and wait for approval.
2. For each approved task (run independent tasks in parallel, each worker in its own worktree if they touch the same files):
   a. Launch the `worker` agent with the task path.
   b. Launch the `validator` agent (fresh context) with the task path.
   c. On FAIL, pass the validator's fixes to a new worker round. Max 3 rounds, then stop and ask the user.
   d. On PASS, set task Status to `validated` and append to its Log.
3. Commit validated tasks on the current branch, one commit per task. Summarise results to the user.
