# factory-kit

Reusable software factory for Claude Code: orchestrator command, four mandatory roles
(**worker**, **validator**, **documentor**, **runbook-refiner**) and a pluggable validation gate.

    factory-kit/install.sh /path/to/project --check node    # or python, static-site, or omit --check

On request (never scheduled), run `/document <task|change|topic>` for the documentor and `/runbook <task|incident|refine>`
for the runbook-refiner, outside the `/factory` loop.

Then edit `scripts/checks.d/` for the project, and run `/factory <goal>` in Claude Code.

Docs check: `scripts/factory-docs-check.py` (deterministic, no agent) replaces the second validator pass; the documentor and
runbook-refiner are skipped when a spec says `none: <reason>` and the validator accepted it.

Model tiering: the documentor and runbook-refiner default to a smaller model (`model: haiku` in their agent files); change it there if your quality guard says so.

Usage metrics: `scripts/factory-metrics.py` builds a per-task token ledger from session transcripts (no model calls);
`/factory-report` (on request) shows the per-task split by role and where to reduce tokens. See `factory/metrics/README.md`.

What it installs: `.claude/agents/*` (4 roles), `.claude/commands/factory.md`, `factory/tasks/_template.md`
(with `Docs impact` and `Runbook impact`), `scripts/validate.sh`, `scripts/checks.d/00-factory-roles.sh`
(fails if a role, the runbook index, or a task's impact sections are missing), `docs/runbooks/` (index + template),
and the factory section of `CLAUDE.md`.

Re-running the installer upgrades kit files and keeps your checks, tasks and runbooks. To adapt an agent to your project
(for example a language-specific worker, or a task template with extra fields), edit it and add the line `<!-- factory-kit: customized -->`: the installer then
leaves it alone (diff it against the kit when upgrading).
To share across projects: copy `factory-kit/` into a standalone repo (or `git subtree split -P factory-kit`) and run its installer on each project.
