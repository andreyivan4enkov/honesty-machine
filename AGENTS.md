# AGENTS.md — Honesty Contract for AI Agents

Drop this file into your repository root. Any agent (Claude Code, Cursor, Codex,
DeepSeek Harness, Aider, …) that reads AGENTS.md will follow it. Enforcement is
mechanical (pre-commit + watcher), so the contract does not rely on agent goodwill.

## The one rule

**Never report a result you did not reproduce. The reviewer reruns your code — always.**

## Process for every claim

1. **Claim** — state the thesis verbatim, with an ID.
2. **Code** — implement it as a *saved, runnable script* in the repo.
   A one-off inline measurement is a process violation: it cannot be rerun.
3. **Measurement** — run it. Deterministic runs must match on repeat ("СОВПАЛО" / MATCHED).
4. **Baselines** — every number ships next to its baseline and the random level.
   A claim without a baseline in the same report is not a claim, it is marketing.
5. **Verdict** — ✅ confirmed / ⚠️ partial / ❌ refuted / not tested.
   Record the verdict in the results table. Never overwrite a working version — version files.
6. **Report both** — what worked AND what did not. Never switch the metric mid-report.

## Mechanical enforcement

- Before committing code, run: `python3 honest_audit.py <changed files>`
- The pre-commit hook blocks commits containing BLOCK-severity fraud.
- WARN findings are allowed only with an explicit human-judged justification
  written in the commit message (example: "argmax in measurement harness only").

## Forbidden without explicit operator approval

- Introducing mechanisms listed as `block` severity in `honesty_patterns.json`.
- Deleting or weakening `honesty_patterns.json`, the pre-commit hook, or the watcher.
- Claiming victory over a baseline measured on different data than the win.
- Numbers "from memory" or from chat history: only artifacts count.

## If you find fraud (including your own past output)

1. Do not silently fix. Record: file, category, how it was found.
2. Move offending code to a quarantine folder with a manifest (path → reason).
3. Rebuild honestly, rerun, report both the fraud and the fix.

The full reasoning behind every rule: `docs/METHODOLOGY.md`.
Real caught cases these rules come from: `docs/CASES.md`.
