# factory-kit

Reusable software factory for Claude Code: orchestrator command, worker and validator agents, pluggable validation gate.

    factory-kit/install.sh /path/to/project --check node    # or python, static-site, or omit --check

Then edit `scripts/checks.d/` for the project, and run `/factory <goal>` in Claude Code.
To share across projects: copy `factory-kit/` into a standalone repo (or `git subtree split -P factory-kit`) and run its installer on each project.
Re-running the installer upgrades agents/commands/validate.sh and keeps your checks, tasks and CLAUDE.md.
