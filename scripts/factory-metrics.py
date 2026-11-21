#!/usr/bin/env python3
"""factory-metrics: per-task token ledger and review report for the software factory.

Reads Claude Code session transcripts (local JSONL files; no model calls, stdlib only) and keeps an
append-only-by-session ledger at factory/metrics/usage.jsonl.

    factory-metrics.py record   [--session ID | --transcript FILE | --all] [--ledger FILE]
    factory-metrics.py report   [--task NNN] [--ledger FILE] [--out FILE]
    factory-metrics.py selftest

Accuracy notes (see factory/metrics/README.md):
  * The transcript logs one API response on several lines: usage is deduplicated per requestId.
  * An agent result's `totalTokens` / <usage> line is the LAST request's context size, not billed usage.
  * The transcript format is undocumented: unexpected shapes are skipped and counted, never guessed.
"""
import argparse, collections, glob, json, os, re, statistics, sys, tempfile
from datetime import datetime, timezone

LEDGER_DEFAULT = "factory/metrics/usage.jsonl"
PRICES_DEFAULT = "factory/metrics/prices.json"
TAG_RE = re.compile(r"^\W*TASK\s+(\S+?)\s*[·|,\-]\s*round\s+(\d+)\s*[·|,\-]\s*phase\s+([A-Za-z][\w-]*)", re.I)
VERDICT_RE = re.compile(r"^\W*(PASS|FAIL)\b", re.I)
FRESH = ("input", "cache_write_5m", "cache_write_1h", "output")


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def read_jsonl(path):
    out, bad = [], 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    bad += 1
    except OSError:
        return [], 0
    return out, bad


def requests_of(lines):
    """Deduplicate usage per API request. Returns list of dicts sorted by time."""
    best = {}
    for d in lines:
        m = d.get("message")
        if not (isinstance(m, dict) and isinstance(m.get("usage"), dict)):
            continue
        rid = d.get("requestId") or m.get("id") or d.get("uuid")
        u = m["usage"]
        cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
        w5 = cc.get("ephemeral_5m_input_tokens")
        w1 = cc.get("ephemeral_1h_input_tokens")
        total_w = u.get("cache_creation_input_tokens") or 0
        if w5 is None and w1 is None:
            w5, w1 = total_w, 0
        r = {"rid": rid, "t": ts(d["timestamp"]) if d.get("timestamp") else 0.0, "model": m.get("model") or "unknown",
             "input": u.get("input_tokens") or 0, "cache_write_5m": w5 or 0, "cache_write_1h": w1 or 0,
             "cache_read": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0,
             "thinking": ((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0), "d": d}
        prev = best.get(rid)
        if prev is None:
            best[rid] = r
        else:
            first_t = min(prev["t"], r["t"])
            if r["output"] >= prev["output"]:
                r["t"] = first_t
                best[rid] = r
            else:
                prev["t"] = first_t
    return sorted(best.values(), key=lambda x: x["t"])


def tokens_of(reqs):
    t = collections.Counter()
    for r in reqs:
        for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output", "thinking"):
            t[k] += r[k]
    t["requests"] = len(reqs)
    return dict(t)


def tool_uses(lines):
    uses = {}
    for d in lines:
        m = d.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for c in m["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    uses[c.get("id")] = (c.get("name"), c.get("input") if isinstance(c.get("input"), dict) else {})
    return uses


def tool_result_chars(lines, uses):
    """chars of Bash results for validate.sh runs (proxy for gate output tokens) and total tool-result chars."""
    gate = total = 0
    for d in lines:
        m = d.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for c in m["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    content = c.get("content")
                    n = len(content) if isinstance(content, str) else sum(len(x.get("text", "")) for x in content if isinstance(x, dict)) if isinstance(content, list) else 0
                    total += n
                    name, inp = uses.get(c.get("tool_use_id"), (None, {}))
                    if name == "Bash" and "validate.sh" in str(inp.get("command", "")):
                        gate += n
    return gate, total


MSG_RE = re.compile(r'<agent-message from="([^"]+)">\s*(.*?)\s*</agent-message>', re.S)
PHASE_ROLE = {"code": "worker", "validate": "validator", "docs-check": "validator", "docs": "documentor", "runbook": "runbook-refiner"}


def walk_strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from walk_strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk_strings(v)


def collect_reports(lines):
    """Background agents hand their final report back as an <agent-message from="<agentId>"> block."""
    out = {}
    for d in lines:
        for s in walk_strings(d):
            if "<agent-message" not in s:
                continue
            for m in MSG_RE.finditer(s):
                body = m.group(2).split("The report follows:", 1)[-1]
                text = "\n".join(l.strip() for l in body.splitlines()).strip()
                out.setdefault(m.group(1), text)
    return out


def sub_times(lines):
    t = [ts(d["timestamp"]) for d in lines if d.get("timestamp")]
    return (min(t), max(t)) if t else (None, None)


def parse_tag(prompt):
    first = (prompt or "").strip().splitlines()[0] if (prompt or "").strip() else ""
    m = TAG_RE.match(first)
    if not m:
        return "untagged", 0, "?"
    return m.group(1), int(m.group(2)), m.group(3).lower()


def build_rows(session_id, transcripts):
    """A session's transcript can be split across project folders when the working directory changes:
    every part is merged (requests are deduplicated by requestId across parts)."""
    if isinstance(transcripts, str):
        transcripts = [transcripts]
    main, bad = [], 0
    for t in transcripts:
        lines, b = read_jsonl(t)
        main += lines
        bad += b
    sub_dirs = [os.path.join(os.path.dirname(t), session_id, "subagents") for t in transcripts]
    reports = collect_reports(main)
    rows, skipped, seen = [], bad, set()
    for d in main:
        r = d.get("toolUseResult")
        if not (isinstance(r, dict) and r.get("agentId")):
            continue
        aid = r["agentId"]
        if aid in seen:          # split sessions replay earlier results: count each agent once
            continue
        seen.add(aid)
        end = ts(d["timestamp"]) if d.get("timestamp") else 0.0
        dur = (r.get("totalDurationMs") or 0) / 1000.0
        task, rnd, phase = parse_tag(r.get("prompt"))
        sub = []
        for sd in sub_dirs:
            part, b = read_jsonl(os.path.join(sd, f"agent-{aid}.jsonl"))
            sub += part
            skipped += b
        reqs = requests_of(sub)
        if not reqs:
            skipped += 1
            continue
        meta = {}
        for sd in sub_dirs:
            try:
                meta = json.load(open(os.path.join(sd, f"agent-{aid}.meta.json"))) or meta
            except (OSError, ValueError):
                pass
        t0, t1 = sub_times(sub)
        if t0 is not None:
            end, dur = t1, t1 - t0          # the agent's own transcript is the reliable clock
        uses = tool_uses(sub)
        reads = sorted({i.get("file_path") for n, i in uses.values() if n == "Read" and i.get("file_path")})
        gate_chars, total_chars = tool_result_chars(sub, uses)
        hb = r.get("handbackReport")
        text = hb.get("text") if isinstance(hb, dict) else (hb if isinstance(hb, str) else "")
        text = text or reports.get(aid, "")
        v = VERDICT_RE.match(text.strip().splitlines()[0]) if text.strip() else None
        first = reqs[0]
        row = {"v": 1, "kind": "agent", "session": session_id, "agent_id": aid, "agent_type": r.get("agentType") or meta.get("agentType") or PHASE_ROLE.get(phase, "unknown"),
               "task": task, "round": rnd, "phase": phase, "model": r.get("resolvedModel") or first["model"],
               "start": end - dur, "end": end, "duration_ms": int(dur * 1000) or r.get("totalDurationMs") or 0,
               "prefix_tokens": first["input"] + first["cache_write_5m"] + first["cache_write_1h"] + first["cache_read"],
               "tool_calls": len(uses), "reads": reads, "gate_output_chars": gate_chars, "tool_result_chars": total_chars,
               "verdict": v.group(1).upper() if v else None, "unverified": text.count("UNVERIFIED"),
               "report_words": len(text.split())}
        row.update(tokens_of(reqs))
        rows.append(row)
    # orchestrator (main session) requests attributed to task windows
    windows = collections.defaultdict(lambda: [float("inf"), 0.0])
    for row in rows:
        if row["task"] not in ("untagged",):
            w = windows[row["task"]]
            w[0], w[1] = min(w[0], row["start"]), max(w[1], row["end"])
    buckets = collections.defaultdict(list)
    for q in requests_of(main):
        hit = [t for t, (a, b) in windows.items() if a <= q["t"] <= b]
        key = hit[0] if len(hit) == 1 else ("shared" if len(hit) > 1 else "unattributed")
        buckets[(key, q["model"])].append(q)
    for (task, model), qs in sorted(buckets.items()):
        row = {"v": 1, "kind": "orchestrator", "session": session_id, "agent_id": None, "agent_type": "orchestrator", "task": task,
               "round": 0, "phase": "orchestrate", "model": model, "start": qs[0]["t"], "end": qs[-1]["t"], "duration_ms": 0,
               "prefix_tokens": 0, "tool_calls": 0, "reads": [], "gate_output_chars": 0, "tool_result_chars": 0,
               "verdict": None, "unverified": 0, "report_words": 0}
        row.update(tokens_of(qs))
        rows.append(row)
    return rows, skipped


def find_transcripts(args):
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")), "projects")
    if args.transcript:
        p = os.path.abspath(args.transcript)
        return [(os.path.splitext(os.path.basename(p))[0], [p])]
    sid = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        sys.exit("factory-metrics: no session: set CLAUDE_CODE_SESSION_ID or pass --session / --transcript")
    hits = sorted(glob.glob(os.path.join(base, "*", f"{sid}.jsonl")))
    if not hits:
        sys.exit(f"factory-metrics: transcript for session {sid} not found under {base} (transcripts live only while the container does; record before the session ends)")
    if args.all:
        groups = collections.defaultdict(list)
        for d in sorted({os.path.dirname(h) for h in hits}):
            for p in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
                groups[os.path.splitext(os.path.basename(p))[0]].append(p)
        return sorted(groups.items())
    return [(sid, hits)]


def load_ledger(path):
    rows = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cmd_record(args):
    keep = load_ledger(args.ledger)
    total_new, skipped = 0, 0
    for sid, paths in find_transcripts(args):
        rows, sk = build_rows(sid, paths)
        skipped += sk
        keep = [r for r in keep if r.get("session") != sid] + rows
        total_new += len(rows)
    keep.sort(key=lambda r: (r.get("start", 0), r.get("agent_id") or ""))
    os.makedirs(os.path.dirname(os.path.abspath(args.ledger)), exist_ok=True)
    with open(args.ledger, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"factory-metrics: ledger {args.ledger}: {len(keep)} rows ({total_new} from this record, {skipped} unreadable/unexpected lines skipped)")


# ---------------------------------------------------------------- report
def load_prices():
    try:
        p = json.load(open(PRICES_DEFAULT))
        return p.get("per_million_tokens", {})
    except (OSError, ValueError):
        return {}


def cost(row, prices):
    p = prices.get(row["model"])
    need = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
    if not p or any(p.get(k) is None for k in need):
        return None
    return sum(row.get(k, 0) * p[k] for k in need) / 1e6


def fresh(row):
    return sum(row.get(k, 0) for k in FRESH)


def fmt(n):
    return f"{n:,}"


def money(x):
    return "n/a" if x is None else f"${x:,.2f}"


def role_key(r):
    if r["kind"] != "agent":
        return "orchestrator"
    if r["agent_type"] in (None, "", "unknown"):
        return PHASE_ROLE.get(r["phase"], "unknown")
    return r["agent_type"]


def task_files(task):
    g = glob.glob(f"factory/tasks/{task}-*.md")
    return g[0] if g else None


def spec_says_none(task, section):
    p = task_files(task)
    if not p:
        return False
    t = open(p, encoding="utf-8").read()
    m = re.search(r"^## " + re.escape(section) + r"\s*\n(.*?)(?=^## |\Z)", t, re.S | re.M)
    return bool(m and m.group(1).strip().lower().startswith("none"))


def cmd_report(args):
    rows = load_ledger(args.ledger)
    if not rows:
        sys.exit(f"factory-metrics: ledger {args.ledger} is empty: run `record` first")
    prices = load_prices()
    priced = any(cost(r, prices) is not None for r in rows)
    out = []
    w = out.append
    tasks = sorted({r["task"] for r in rows}, key=lambda t: (not t.isdigit(), t))
    if args.task:
        tasks = [t for t in tasks if t == args.task]
    w("# Factory usage report\n")
    w(f"Ledger: `{args.ledger}`: {len(rows)} rows, {len({r['session'] for r in rows})} session(s). "
      "Usage is deduplicated per API request. " + ("Cost is an estimate from `prices.json`; your provider console is authoritative.\n" if priced
      else "**Cost: n/a: fill `factory/metrics/prices.json` (per-million-token prices for each model) to see dollars.** Shares below use fresh tokens (input + cache writes + output).\n"))
    w("`cache read` is cheap per token but large; it is shown separately and not counted in 'fresh'.\n")

    # per-task split
    w("## Per task, split by role\n")
    for t in tasks:
        tr = [r for r in rows if r["task"] == t]
        tot_cost = [cost(r, prices) for r in tr]
        task_cost = sum(c for c in tot_cost if c is not None) if priced else None
        task_fresh = sum(fresh(r) for r in tr) or 1
        rounds = max([r["round"] for r in tr if r["kind"] == "agent"] or [0])
        verdicts = [r["verdict"] for r in sorted(tr, key=lambda x: x["start"]) if r["verdict"]]
        w(f"### Task {t}: {sum(1 for r in tr if r['kind']=='agent')} launches, rounds {rounds}, verdicts {'→'.join(verdicts) or 'n/a'}"
          + (f", est. {money(task_cost)}" if priced else "") + "\n")
        w("| role · phase · model | launches | requests | input | cache write | cache read | output | share | est. cost |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        groups = collections.defaultdict(list)
        for r in tr:
            groups[(role_key(r), r["phase"], r["model"])].append(r)
        for (role, phase, model), g in sorted(groups.items(), key=lambda kv: -sum(fresh(x) for x in kv[1])):
            f_ = sum(fresh(x) for x in g)
            c = [cost(x, prices) for x in g]
            share = (sum(x for x in c if x is not None) / task_cost if task_cost else f_ / task_fresh)
            w(f"| {role} · {phase} · {model} | {sum(1 for x in g if x['kind']=='agent') or '-'} | {fmt(sum(x['requests'] for x in g))} | "
              f"{fmt(sum(x['input'] for x in g))} | {fmt(sum(x['cache_write_5m']+x['cache_write_1h'] for x in g))} | "
              f"{fmt(sum(x['cache_read'] for x in g))} | {fmt(sum(x['output'] for x in g))} | {share:.0%} | "
              f"{money(sum(x for x in c if x is not None)) if priced else 'n/a'} |")
        w("")

    # cross-task review
    ag = [r for r in rows if r["kind"] == "agent"]
    w("## Cross-task review: where tokens go and which refinement it points to\n")
    by_role = collections.defaultdict(list)
    for r in rows:
        by_role[role_key(r)].append(r)
    total_fresh = sum(fresh(r) for r in rows) or 1
    w("**Fresh tokens by role** (all tasks)\n")
    w("| role | launches | fresh tokens | share | cache read | est. cost |")
    w("|---|---:|---:|---:|---:|---:|")
    for role, g in sorted(by_role.items(), key=lambda kv: -sum(fresh(x) for x in kv[1])):
        c = sum(x for x in (cost(r, prices) for r in g) if x is not None)
        w(f"| {role} | {sum(1 for x in g if x['kind']=='agent') or '-'} | {fmt(sum(fresh(x) for x in g))} | {sum(fresh(x) for x in g)/total_fresh:.0%} | {fmt(sum(x['cache_read'] for x in g))} | {money(c) if priced else 'n/a'} |")
    w("")

    numeric = [t for t in tasks if t.isdigit()]
    per_task_launch = {t: sum(1 for r in ag if r["task"] == t) for t in numeric}
    if per_task_launch:
        avg = statistics.mean(per_task_launch.values())
        w(f"**Launches per task:** average {avg:.1f} (max {max(per_task_launch.values())}). Each launch pays a cold-start prefix (below); fewer launches is the biggest lever.\n")

    flag = []
    for t in numeric:
        for sec, role, ref in (("Docs impact", "documentor", "1"), ("Runbook impact", "runbook-refiner", "1")):
            if spec_says_none(t, sec):
                n = [r for r in ag if r["task"] == t and r["agent_type"] == role]
                if n:
                    flag.append((t, role, len(n), sum(fresh(x) for x in n), ref))
    w("**Launches the spec said were unnecessary (`none: <reason>`)**: refinement 1\n")
    w("| task | role | launches | fresh tokens |\n|---|---|---:|---:|" if flag else "_none found_")
    for f_ in flag:
        w(f"| {f_[0]} | {f_[1]} | {f_[2]} | {fmt(f_[3])} |")
    w("")

    dc = [r for r in ag if r["agent_type"] == "validator" and r["phase"] == "docs-check"]
    cv = [r for r in ag if r["agent_type"] == "validator" and r["phase"] != "docs-check"]
    w(f"**Second validator pass (phase docs-check):** {len(dc)} launches, {fmt(sum(fresh(x) for x in dc))} fresh tokens vs {fmt(sum(fresh(x) for x in cv))} for the code validations: refinement 2\n")

    gate = [r for r in ag if r["gate_output_chars"]]
    gc = sum(r["gate_output_chars"] for r in gate)
    w(f"**Gate output read by agents:** {fmt(gc)} characters (~{fmt(gc//4)} tokens, 4 chars/token estimate) across {len(gate)} agents: refinement 3\n")

    big = sorted(ag, key=lambda r: -r["report_words"])[:3]
    w("**Longest agent reports (words) and orchestrator share:** refinement 4\n")
    for r in big:
        w(f"- task {r['task']} {r['agent_type']} {r['phase']}: {r['report_words']} words, {fmt(r['output'])} output tokens")
    orch = by_role.get("orchestrator", [])
    w(f"- orchestrator: {fmt(sum(fresh(x) for x in orch))} fresh tokens, {fmt(sum(x['cache_read'] for x in orch))} cache-read tokens ({sum(fresh(x) for x in orch)/total_fresh:.0%} of all fresh tokens)\n")

    w("**Role × model with quality guard** (refinement 5: only downgrade a model where rework does not rise)\n")
    w("| role | model | launches | avg fresh/launch | PASS | FAIL | UNVERIFIED mentions |\n|---|---|---:|---:|---:|---:|---:|")
    rm = collections.defaultdict(list)
    for r in ag:
        rm[(r["agent_type"], r["model"])].append(r)
    for (role, model), g in sorted(rm.items()):
        w(f"| {role} | {model} | {len(g)} | {fmt(sum(fresh(x) for x in g)//len(g))} | {sum(1 for x in g if x['verdict']=='PASS')} | {sum(1 for x in g if x['verdict']=='FAIL')} | {sum(x['unverified'] for x in g)} |")
    w("")

    rework = []
    for t in numeric:
        tr = [r for r in ag if r["task"] == t]
        late = [r for r in tr if r["round"] > 1 and r["phase"] in ("code", "validate")]
        if late:
            rework.append((t, max(r["round"] for r in tr), sum(fresh(x) for x in late), sum(fresh(x) for x in tr)))
    w("**Rework (rounds above 1 on code/validate):** better specs and test-linked criteria: refinement 6\n")
    if rework:
        w("| task | rounds | rework fresh tokens | share of task |\n|---|---:|---:|---:|")
        for t, rd, a, b in rework:
            w(f"| {t} | {rd} | {fmt(a)} | {a/(b or 1):.0%} |")
    else:
        w("_none: every task passed in round 1_")
    w("")

    reads = collections.defaultdict(set)
    for r in ag:
        for p in r["reads"]:
            reads[(r["task"], p)].add(r["agent_id"])
    rep = sorted(((len(a), t, p) for (t, p), a in reads.items() if len(a) >= 3), reverse=True)[:8]
    w("**Same file read by 3+ agents in one task** (section-scoped refs or summaries): refinement 8\n")
    for n, t, p in rep:
        w(f"- {p}: {n} agents (task {t})")
    if not rep:
        w("_none_")
    w("")

    pref = collections.defaultdict(list)
    for r in ag:
        pref[r["agent_type"]].append(r["prefix_tokens"])
    w("**Cold-start prefix and cache efficiency per role** (refinements 10 and 'restrict tools')\n")
    w("| role | median prefix tokens | cache-read ratio |\n|---|---:|---:|")
    for role, v in sorted(pref.items()):
        g = [r for r in ag if r["agent_type"] == role]
        rd = sum(x["cache_read"] for x in g)
        den = rd + sum(x["input"] + x["cache_write_5m"] + x["cache_write_1h"] for x in g) or 1
        w(f"| {role} | {fmt(int(statistics.median(v)))} | {rd/den:.0%} |")
    w("")
    w("_Attribution notes: orchestrator requests are assigned to the task whose agent-launch window contains them; requests between tasks are `unattributed`, overlapping windows are `shared`._")
    text = "\n".join(out) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w", encoding="utf-8").write(text)
        print(f"factory-metrics: report written to {args.out}")
    else:
        sys.stdout.write(text)


# ---------------------------------------------------------------- selftest
def _u(inp, w5, rd, out, w1=0):
    return {"input_tokens": inp, "cache_creation_input_tokens": w5 + w1, "cache_read_input_tokens": rd, "output_tokens": out,
            "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}, "output_tokens_details": {"thinking_tokens": 1}}


def _asst(rid, t, model, usage, content=None):
    return {"type": "assistant", "requestId": rid, "timestamp": t, "message": {"model": model, "usage": usage, "content": content or []}}


def cmd_selftest(_):
    tmp = tempfile.mkdtemp()
    sid = "sess-1"
    sub_dir = os.path.join(tmp, sid, "subagents")
    os.makedirs(sub_dir)

    def w_jsonl(path, items):
        with open(path, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
    # subagent A: worker, task 007 round 1 (duplicate lines for request r1; Read x2; gate run)
    A = [_asst("r1", "2026-01-01T00:00:10Z", "m-a", _u(2, 100, 0, 5), [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "docs/a.md"}}]),
         _asst("r1", "2026-01-01T00:00:10.5Z", "m-a", _u(2, 100, 0, 50)),
         {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 40}]}},
         _asst("r2", "2026-01-01T00:00:20Z", "m-a", _u(2, 10, 100, 20), [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "scripts/validate.sh"}}]),
         {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "y" * 400}]}}]
    B = [_asst("q1", "2026-01-01T00:01:10Z", "m-b", _u(2, 60, 0, 30), [{"type": "tool_use", "id": "t9", "name": "Read", "input": {"file_path": "docs/a.md"}}])]
    w_jsonl(os.path.join(sub_dir, "agent-aaa.jsonl"), A)
    w_jsonl(os.path.join(sub_dir, "agent-bbb.jsonl"), B)
    main = [_asst("m1", "2026-01-01T00:00:01Z", "m-o", _u(1, 1000, 0, 10)),   # before any window: unattributed
            _asst("m2", "2026-01-01T00:00:15Z", "m-o", _u(1, 5, 2000, 40)),    # inside task 007 window
            {"type": "user", "timestamp": "2026-01-01T00:00:30Z", "toolUseResult": {"agentId": "aaa", "agentType": "worker", "prompt": "TASK 007 · round 1 · phase code\nDo it", "resolvedModel": "m-a", "totalDurationMs": 25000,
             "handbackReport": {"text": "files changed: x\nUNVERIFIED y"}}},
            {"type": "user", "timestamp": "2026-01-01T00:01:20Z", "toolUseResult": {"agentId": "bbb", "agentType": "validator", "prompt": "TASK 007 · round 1 · phase validate", "resolvedModel": "m-b", "totalDurationMs": 15000,
             "handbackReport": {"text": "PASS\n- ok"}}},
            {"type": "user", "timestamp": "2026-01-01T00:01:30Z", "toolUseResult": {"stdout": "not an agent"}}]
    tp = os.path.join(tmp, sid + ".jsonl")
    w_jsonl(tp, main)
    rows, skipped = build_rows(sid, tp)
    ag = {r["agent_id"]: r for r in rows if r["kind"] == "agent"}
    assert skipped == 0, skipped
    a = ag["aaa"]
    assert (a["task"], a["round"], a["phase"]) == ("007", 1, "code"), a
    assert a["requests"] == 2 and a["input"] == 4 and a["cache_write_5m"] == 110 and a["cache_read"] == 100 and a["output"] == 70, a   # r1 deduped to its fullest line
    assert a["prefix_tokens"] == 102, a
    assert a["reads"] == ["docs/a.md"] and a["gate_output_chars"] == 400 and a["unverified"] == 1, a
    b = ag["bbb"]
    assert b["verdict"] == "PASS" and b["phase"] == "validate", b
    o = {r["task"]: r for r in rows if r["kind"] == "orchestrator"}
    assert o["007"]["cache_read"] == 2000 and o["unattributed"]["cache_write_5m"] == 1000, o
    # the same session split across two project folders (working directory changed mid-session)
    tmp2 = tempfile.mkdtemp()
    sub2 = os.path.join(tmp2, sid, "subagents")
    os.makedirs(sub2)
    w_jsonl(os.path.join(sub2, "agent-ccc.jsonl"), [_asst("c1", "2026-01-01T00:05:10Z", "m-c", _u(2, 30, 0, 9))])
    tp2 = os.path.join(tmp2, sid + ".jsonl")
    w_jsonl(tp2, [_asst("m2", "2026-01-01T00:00:15Z", "m-o", _u(1, 5, 2000, 40)),   # replayed from part 1: must not be counted twice
                  {"type": "user", "timestamp": "2026-01-01T00:00:30Z", "toolUseResult": {"agentId": "aaa", "agentType": "worker", "prompt": "TASK 007 · round 1 · phase code", "resolvedModel": "m-a", "totalDurationMs": 25000, "handbackReport": {"text": "x"}}},
                  _asst("m3", "2026-01-01T00:05:05Z", "m-o", _u(1, 7, 100, 3)),
                  {"type": "user", "timestamp": "2026-01-01T00:05:20Z", "toolUseResult": {"agentId": "ccc", "agentType": "documentor", "prompt": "TASK 007 · round 1 · phase docs", "resolvedModel": "m-c", "totalDurationMs": 15000,
                   "handbackReport": {"text": "done"}}}])
    both, sk2 = build_rows(sid, [tp, tp2])
    assert sk2 == 0 and {r["agent_id"] for r in both if r["kind"] == "agent"} == {"aaa", "bbb", "ccc"}, both
    assert [r["cache_write_5m"] for r in both if r["agent_id"] == "ccc"] == [30]
    assert sum(1 for r in both if r["agent_id"] == "aaa") == 1, "replayed agent results must be counted once"
    assert sum(r["cache_read"] for r in both if r["kind"] == "orchestrator") == 2000 + 100, "replayed requests counted once"
    # background agent: no agentType / report in the launch result; type from meta.json, report from the hand-back message
    sub3 = os.path.join(tmp, sid, "subagents")
    w_jsonl(os.path.join(sub3, "agent-ddd.jsonl"), [_asst("d1", "2026-01-01T00:06:00Z", "m-d", _u(2, 40, 0, 11)), _asst("d2", "2026-01-01T00:07:00Z", "m-d", _u(2, 5, 40, 12))])
    json.dump({"agentType": "validator", "description": "x"}, open(os.path.join(sub3, "agent-ddd.meta.json"), "w"))
    asyncmain = main + [{"type": "user", "timestamp": "2026-01-01T00:06:00Z", "toolUseResult": {"agentId": "ddd", "prompt": "TASK 007 · round 2 · phase docs-check", "status": "async_launched"}},
                        {"type": "attachment", "timestamp": "2026-01-01T00:07:05Z", "attachment": {"type": "queued_command", "prompt": '<agent-message from="ddd">\n[Subagent hand-back] ... The report follows:\n  PASS\n  - ok UNVERIFIED x\n</agent-message>'}}]
    tp3 = os.path.join(tmp, "sess-async.jsonl")
    w_jsonl(tp3, asyncmain)
    rows3, sk3 = build_rows("sess-1", [tp3])
    d = [r for r in rows3 if r.get("agent_id") == "ddd"][0]
    assert d["agent_type"] == "validator" and d["verdict"] == "PASS" and d["unverified"] == 1, d
    assert d["duration_ms"] == 60000 and d["phase"] == "docs-check", d
    ledger = os.path.join(tmp, "usage.jsonl")
    ns = argparse.Namespace(transcript=tp, session=None, all=False, ledger=ledger)
    cmd_record(ns)
    first = open(ledger).read()
    cmd_record(ns)
    assert open(ledger).read() == first, "record must be idempotent"
    assert len(load_ledger(ledger)) == len(rows)
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        import io
        buf, old = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            cmd_report(argparse.Namespace(ledger=ledger, task=None, out=None))
        finally:
            sys.stdout = old
    finally:
        os.chdir(cwd)
    txt = buf.getvalue()
    assert "### Task 007" in txt and "Cross-task review" in txt and "Cost: n/a" in txt, txt[:400]
    assert parse_tag("task 12 - round 2 - phase docs-check") == ("12", 2, "docs-check")
    assert parse_tag("nothing") == ("untagged", 0, "?")
    print("factory-metrics selftest: OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("record")
    r.add_argument("--session"); r.add_argument("--transcript"); r.add_argument("--all", action="store_true")
    r.add_argument("--ledger", default=LEDGER_DEFAULT)
    r.set_defaults(fn=cmd_record)
    p = sp.add_parser("report")
    p.add_argument("--task"); p.add_argument("--ledger", default=LEDGER_DEFAULT); p.add_argument("--out")
    p.set_defaults(fn=cmd_report)
    sp.add_parser("selftest").set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
