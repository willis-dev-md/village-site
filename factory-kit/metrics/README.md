# Factory metrics

Per-launch token ledger for the software factory: `usage.jsonl` (one JSON row per agent launch, plus orchestrator rows),
built by `scripts/factory-metrics.py` from Claude Code's local session transcripts. No model calls, standard library only.

    python3 scripts/factory-metrics.py record               # add this session to the ledger (idempotent)
    python3 scripts/factory-metrics.py report [--task 005]  # per-task split + cross-task review
    /factory-report                                         # same, on request, via Claude Code

## How it works
- Every factory agent prompt starts with a tag line: `TASK <NNN> · round <R> · phase <code|validate|docs|runbook|docs-check>`.
  The orchestrator commands do this; untagged launches are grouped as task `untagged`.
- `record` reads the session transcript (`~/.claude/projects/*/<session>.jsonl`) and each subagent's transcript
  (`<session>/subagents/agent-<id>.jsonl`), and writes rows: role (agent type), task, round, phase, model, tokens
  (input, cache write 5m/1h, cache read, output, thinking), requests, tool calls, files read (paths only), PASS/FAIL verdict,
  number of UNVERIFIED mentions, report length, cold-start prefix size, gate-output size. No prompt or file content is stored.
- Orchestrator (main-session) requests are attributed to the task whose agent-launch window contains them; requests between
  tasks are `unattributed`; overlapping windows are `shared`. This is an estimate.
- The ledger is committed with the work. Transcripts live only as long as the container, so record at the end of each task.

## Accuracy rules (learned by checking real transcripts)
1. **Deduplicate per request.** One API response is logged on several lines; summing raw lines overcounts by about 2 to 2.6x.
   The script keeps one record per `requestId`.
2. **`totalTokens` and the `<usage>` line in an agent result are not billed usage.** They equal the *last* request's context size
   (input + cache write + cache read + output). Cost is computed from per-request usage instead.
3. **Cold start matters.** A launch's first request carries its whole prefix (system prompt, tools, CLAUDE.md). An all-tools agent
   measured about 55K tokens; a restricted-tool role about 8.7K. Keep each role's `tools:` list minimal.
4. **The transcript format is undocumented.** The script skips and counts lines it does not understand and never guesses;
   `selftest` (run by the gate) pins the shapes it relies on. If a Claude Code upgrade changes them, the gate fails loudly.

## Cost
Dollars need prices. Fill `prices.json` (per million tokens, for each model you use: input, output, cache write 5m, cache write 1h,
cache read) from your provider's pricing page; the report shows `n/a` until all five are set for a model. Estimates only: your
provider console is authoritative.
