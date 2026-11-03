#!/usr/bin/env bash
# Deterministic checks for the static site. Exit non-zero on any failure.
set -u
cd "$(dirname "$0")/.."
fail=0
err() { echo "FAIL: $*"; fail=1; }

for f in index.html styles.css script.js; do [ -s "$f" ] || err "$f missing or empty"; done

if command -v node >/dev/null; then
  node --check script.js || err "script.js syntax error"
fi

python3 - <<'PY' || fail=1
import re, sys, os
from html.parser import HTMLParser
html = open("index.html", encoding="utf-8").read()
bad = 0
class P(HTMLParser):
    def __init__(s): super().__init__(); s.ids=set(); s.refs=[]; s.local=[]; s.imgs=[]
    def handle_starttag(s, t, a):
        a = dict(a)
        if "id" in a:
            if a["id"] in s.ids: print("FAIL: duplicate id", a["id"]); global bad; bad = 1
            s.ids.add(a["id"])
        if t == "a" and a.get("href","").startswith("#") and len(a["href"])>1: s.refs.append(a["href"][1:])
        for k in ("src","href"):
            v = a.get(k)
            if v and not re.match(r"^(https?:|mailto:|tel:|#|data:)", v): s.local.append(v)
        if t == "img" and "alt" not in a: s.imgs.append(a.get("src"))
p = P(); p.feed(html)
for r in p.refs:
    if r not in p.ids: print("FAIL: broken anchor #"+r); bad = 1
for l in p.local:
    if not os.path.exists(l.split("?")[0].split("#")[0]): print("FAIL: missing local file", l); bad = 1
for i in p.imgs: print("FAIL: img without alt", i); bad = 1
sys.exit(bad)
PY

[ $fail -eq 0 ] && echo "validate: OK" || { echo "validate: FAILED"; exit 1; }
