# Runbook: Run the site locally

**Owner role:** developer  |  **Severity if this happens:** low
**Last verified:** 2026-11-20, 12f0357

## When to use
Previewing a change before committing, or checking a reported problem on your machine.

## Prerequisites
`python3` (any 3.x). No build step, no dependencies.

## Steps
1. `cd` to the repo root.
2. `python3 -m http.server 8000`  *(expected: `Serving HTTP on 0.0.0.0 port 8000`)*
3. Open http://localhost:8000. `index.html`, `styles.css` and `script.js` each return HTTP 200.
4. Stop with Ctrl+C.

## Troubleshooting
| Symptom | Diagnosis | Fix |
|---|---|---|
| `OSError: [Errno 98] Address already in use` | another process holds the port | use another port: `python3 -m http.server 8001` |
| Page unstyled or filters/name picker do nothing | `styles.css`/`script.js` 404 (served from the wrong directory) | run the command from the repo root (the folder with `index.html`) |
| Old content after an edit | browser cache | hard refresh (Ctrl+Shift+R) |
| `scripts/validate.sh` fails | a check in `scripts/checks.d/` found a problem | read the `FAIL:` lines; they name the file and rule |

## Verify
`curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/` prints `200`.

## Roll back / undo
Nothing is changed by serving. Stop the server.

## Escalate
Repo owner, with the exact error text and your Python version (`python3 --version`).
