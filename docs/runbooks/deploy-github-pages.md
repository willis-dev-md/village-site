# Runbook: Deploy to GitHub Pages

**Owner role:** repo owner  |  **Severity if this happens:** medium
**Last verified:** UNVERIFIED (steps come from the README; they need repo admin rights and could not be run from this environment)

## When to use
First publication of the site, or when the live site does not match `main`.

## Prerequisites
Admin access to the GitHub repository. The `.nojekyll` file stays in the repo root (it stops Jekyll processing).

## Steps
1. Repo **Settings → Pages**.
2. Source: **Deploy from a branch**; branch `main`, folder `/ (root)`; save.
3. Wait for the Pages build (Actions tab → "pages build and deployment"), then open the site URL shown in Settings → Pages.

## Troubleshooting
| Symptom | Diagnosis | Fix |
|---|---|---|
| 404 on the site URL | Pages not enabled, wrong branch/folder, or the first build has not finished | recheck steps 1 to 3; wait a few minutes |
| Old content is live | change is not on `main`, or the build failed | confirm the commit is on `main`; open the failed run in Actions |
| Page loads without styles | wrong base path or file name case | links must be relative (`styles.css`) and match case exactly |

## Verify
The live URL shows the latest `main` content; `curl -I <url>` returns 200.

## Roll back / undo
Revert the commit on `main` (Pages redeploys), or switch the source off in Settings → Pages.

## Escalate
Repo owner; include the failed workflow run link.
