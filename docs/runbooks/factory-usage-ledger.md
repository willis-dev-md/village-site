# Runbook: Record and read factory token usage

**Owner role:** orchestrator / factory owner  |  **Severity if this happens:** low
**Last verified:** 2026-11-20, 59f16f3 (self-test and a real-transcript dry run executed; cost figures need prices filled in)

## When to use
After a factory task or session, to keep the usage ledger up to date; or when the user asks where tokens went (`/factory-report`).

## Prerequisites
Python 3. Run inside the Claude Code session whose transcript you want (the session id is in `CLAUDE_CODE_SESSION_ID`).
Transcripts exist only while the container lives: record before the session ends.

## Steps
1. `python3 scripts/factory-metrics.py record`  *(expected: `ledger factory/metrics/usage.jsonl: N rows ...`, with 0 lines skipped)*
2. `python3 scripts/factory-metrics.py report` (or `--task 005`, `--out factory/metrics/report.md`)  *(expected: a per-task table per role, then the cross-task review)*
3. Commit `factory/metrics/usage.jsonl` with the task's work.
4. For dollars, fill `factory/metrics/prices.json` (per million tokens, per model) from your provider's pricing page.

## Troubleshooting
| Symptom | Diagnosis | Fix |
|---|---|---|
| `no session: set CLAUDE_CODE_SESSION_ID or pass --session / --transcript` | not inside a Claude Code session | pass `--transcript <file>.jsonl` |
| `transcript for session ... not found` | container was replaced or the config dir differs | set `CLAUDE_CONFIG_DIR`, or record from the session itself; usage from a vanished container cannot be recovered |
| `N unreadable/unexpected lines skipped` is large | Claude Code changed its transcript format | run `python3 -I scripts/factory-metrics.py selftest`; update the parser and the self-test together |
| Gate fails with "factory-metrics selftest failed" | the parser or its pinned transcript shapes broke | run the self-test directly and read the assertion |
| Tokens look 2x too high compared with another tool | raw transcript lines were summed | this script deduplicates per `requestId`; use its numbers |
| An agent result shows `subagent_tokens: N` and N seems small | that value is the last request's context size, not billed usage | ignore it; use the ledger |
| Cost shows n/a | `prices.json` has null prices for that model | fill all five prices for the model |

## Verify
`python3 -I scripts/factory-metrics.py selftest` prints `factory-metrics selftest: OK`; `record` twice leaves the ledger unchanged (idempotent).

## Roll back / undo
The ledger is a normal file in git: revert or delete `factory/metrics/usage.jsonl` and record again.

## Escalate
Factory owner, with the `record` output and your Claude Code version.
