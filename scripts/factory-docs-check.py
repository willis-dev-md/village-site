#!/usr/bin/env python3
"""factory-docs-check: deterministic replacement for the second (docs-check) validator pass.

    factory-docs-check.py snapshot NNN   # right after the code validator returns PASS
    factory-docs-check.py check NNN      # after the documentor / runbook-refiner ran
    factory-docs-check.py selftest

check fails when: a non-documentation file changed since the snapshot; the spec's Docs impact / Runbook impact is not `none:`
but no matching documentation / runbook changed; a changed doc has a broken relative link; a changed runbook has not exactly
one "Last verified" line or contains stale wording ("uncommitted"); or a command block tagged `<!-- verify -->` (or
`<!-- verify: db -->`, which gets DATABASE_URL from scripts/testdb.sh) fails when re-run. It WARNs when a documentation file named
in the spec did not change. Exit 0 = no FAIL. No model calls, standard library only.
"""
import hashlib, os, re, subprocess, sys, tempfile, json

STATE_DIR = "factory/.state"
DOC_FILES = {"README.md", "CHANGELOG.md", "CLAUDE.md"}
DOC_PREFIXES = ("docs/", "factory/tasks/", "factory/metrics/")
VERIFY_RE = re.compile(r"<!--\s*verify(?::\s*(db))?\s*-->\s*\n```(?:bash|sh)\n(.*?)\n```", re.S)


def is_doc(p):
    return p in DOC_FILES or p.startswith(DOC_PREFIXES)


def files():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True).stdout
    return sorted(f for f in out.splitlines() if f and not f.startswith(STATE_DIR + "/") and os.path.isfile(f))


def digest():
    d = {}
    for f in files():
        with open(f, "rb") as fh:
            d[f] = hashlib.sha256(fh.read()).hexdigest()
    return d


def spec_path(task):
    import glob
    g = sorted(glob.glob(f"factory/tasks/{task}-*.md"))
    return g[0] if g else None


def section(text, name):
    m = re.search(r"^## " + re.escape(name) + r"\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else None


def cmd_snapshot(task):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(digest(), open(f"{STATE_DIR}/{task}.json", "w"))
    print(f"factory-docs-check: snapshot for task {task} saved ({len(digest())} files)")


def run_blocks(path, text, fails):
    for m in VERIFY_RE.finditer(text):
        needs_db, code = m.group(1), m.group(2)
        env, stop = dict(os.environ), False
        if needs_db:
            if not os.path.exists("scripts/testdb.sh"):
                fails.append(f"{path}: verify block needs a database but scripts/testdb.sh is missing")
                continue
            r = subprocess.run(["bash", "-c", "scripts/testdb.sh start"], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                mm = re.match(r"export (\w+)=(.*)", line)
                if mm:
                    env[mm.group(1)] = mm.group(2).strip("'\"")
            stop = True
        try:
            r = subprocess.run(["bash", "-e", "-c", code], capture_output=True, text=True, env=env, timeout=120)
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                fails.append(f"{path}: verify block failed (exit {r.returncode}): {code.splitlines()[0][:70]} | {' / '.join(tail)[:200]}")
        except subprocess.TimeoutExpired:
            fails.append(f"{path}: verify block timed out: {code.splitlines()[0][:70]}")
        finally:
            if stop:
                subprocess.run(["bash", "-c", "scripts/testdb.sh stop"], capture_output=True)


def cmd_check(task):
    snap_file = f"{STATE_DIR}/{task}.json"
    if not os.path.exists(snap_file):
        sys.exit(f"factory-docs-check: no snapshot for task {task}: run `snapshot {task}` after the code validator passes")
    before, now = json.load(open(snap_file)), digest()
    changed = sorted(f for f in set(before) | set(now) if before.get(f) != now.get(f))
    fails, warns = [], []
    nondoc = [f for f in changed if not is_doc(f)]
    if nondoc:
        fails.append("non-documentation files changed after the code PASS: " + ", ".join(nondoc))
    docs = [f for f in changed if is_doc(f) and f in now]
    runbooks = [f for f in docs if f.startswith("docs/runbooks/")]
    plain = [f for f in docs if not f.startswith(("docs/runbooks/", "factory/"))]
    sp = spec_path(task)
    if not sp:
        fails.append(f"no spec factory/tasks/{task}-*.md")
    else:
        text = open(sp, encoding="utf-8").read()
        for name, have, label in (("Docs impact", plain, "documentation (README/CHANGELOG/docs)"), ("Runbook impact", runbooks, "runbook (docs/runbooks)")):
            s = section(text, name) or ""
            if s.lower().startswith("none"):
                continue
            if not have:
                fails.append(f"spec {name} is not `none` but no {label} file changed")
            for tok in re.findall(r"`([^`\s]+)`", s):
                if re.match(r"^[\w./-]+$", tok) and ("/" in tok or tok.endswith(".md")) and os.path.isfile(tok) and tok not in changed:
                    warns.append(f"spec {name} names {tok} but it did not change (explain in the task Log if intended)")
    for f in docs:
        t = open(f, encoding="utf-8", errors="replace").read()
        if f.endswith(".md"):
            for m in re.finditer(r"\]\(([^)\s]+)\)", t):
                tgt = m.group(1).split("#")[0]
                if tgt and not re.match(r"^(https?:|mailto:)", tgt) and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), tgt))):
                    fails.append(f"{f}: broken link {m.group(1)}")
        if f in runbooks and os.path.basename(f) not in ("README.md", "_template.md"):
            n = len(re.findall(r"Last verified", t))
            if n != 1:
                fails.append(f"{f}: expected exactly one 'Last verified' (found {n})")
            if re.search(r"uncommitted", t, re.I):
                fails.append(f"{f}: stale wording 'uncommitted'")
        run_blocks(f, t, fails)
    unv = sum(open(f, encoding="utf-8", errors="replace").read().count("UNVERIFIED") for f in docs if os.path.isfile(f))
    for w in warns:
        print("WARN:", w)
    for f in fails:
        print("FAIL:", f)
    print(f"factory-docs-check: task {task}: {len(changed)} changed files ({len(docs)} docs, {len(nondoc)} non-docs), {unv} UNVERIFIED mentions, {len(warns)} warnings, {len(fails)} failures")
    sys.exit(1 if fails else 0)


def _w(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w").write(text)


def selftest():
    old = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        subprocess.run(["git", "init", "-q"], check=True)
        _w("README.md", "# r\n")
        _w("docs/a.md", "# a\n")
        _w("docs/runbooks/x.md", "# x\n**Last verified:** d\n")
        _w("src/main.go", "package main\n")
        _w("factory/tasks/001-t.md", "# 1\n## Docs impact\n`README.md`, `docs/a.md`\n\n## Runbook impact\n`docs/runbooks/x.md`\n\n## Status\nin-progress\n")
        _w("factory/tasks/002-t.md", "# 2\n## Docs impact\nnone: nothing user visible here\n\n## Runbook impact\nnone: library only, no operator behaviour\n\n## Status\nin-progress\n")

        def check(task):
            try:
                cmd_check(task)
            except SystemExit as e:
                return e.code
        cmd_snapshot("001")
        assert check("001") == 1, "spec lists docs but nothing changed: must fail"
        _w("README.md", "# r\nnew\n")
        _w("docs/runbooks/x.md", "# x\n**Last verified:** d2\n")
        assert check("001") == 0, "docs and runbook changed: pass (docs/a.md only warns)"
        _w("src/main.go", "package main\n// changed\n")
        assert check("001") == 1, "code changed after PASS: must fail"
        _w("src/main.go", "package main\n")
        _w("docs/a.md", "# a\n[x](missing.md)\n")
        assert check("001") == 1, "broken link: must fail"
        _w("docs/a.md", "# a ok\n")
        _w("docs/runbooks/x.md", "# x\n**Last verified:** d2\nLast verified: d3\n")
        assert check("001") == 1, "two Last verified: must fail"
        _w("docs/runbooks/x.md", "# x\n**Last verified:** d2\n\n<!-- verify -->\n```bash\ntest 1 -eq 2\n```\n")
        assert check("001") == 1, "failing verify block: must fail"
        _w("docs/runbooks/x.md", "# x\n**Last verified:** d2\n\n<!-- verify -->\n```bash\ntest 1 -eq 1\n```\n")
        assert check("001") == 0, "passing verify block: pass"
        cmd_snapshot("002")
        assert check("002") == 0, "none/none with no changes: pass"
        _w("docs/new.md", "# n\n")
        assert check("002") == 0, "docs changed under none: still pass"
    finally:
        os.chdir(old)
    print("factory-docs-check selftest: OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["selftest"]:
        selftest()
    elif len(a) == 2 and a[0] == "snapshot":
        cmd_snapshot(a[1])
    elif len(a) == 2 and a[0] == "check":
        cmd_check(a[1])
    else:
        sys.exit(__doc__)
