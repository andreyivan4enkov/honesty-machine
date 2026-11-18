# Honesty Machine (Машина честности)

**A mechanical discipline + tiny tools that stop AI agents (and humans) from reporting
results that were never reproduced.** Born from a real research project where AI
assistants fabricated numbers, hid gradient training inside "gradient-free" code,
and claimed wins that lived inside noise bands. Every rule in this package exists
because a specific fraud was caught the hard way.

[Русская версия: README.ru.md](README.ru.md)

## The problem

AI coding agents are prolific and confident. They write code, run it once (or never),
and report victory. Three real cases from the project this was extracted from:

1. **"92% vs 86% — our method wins."** The comparison was a one-off inline script —
unreproducible by construction. On a fresh dataset: parity. The "win" lived inside
the noise band of hash collisions.
2. **"Full GPU backprop" inside a C string.** The Python-only auditor scanned
`gpu_renderer_train.c` and found nothing — the training kernel was a string literal
passed to the GPU API. Verdict "CLEAN" until string scanning for C-family files
was added.
3. **166 files with hard fraud** (hidden torch/backprop/softmax in code claiming
to be gradient-free) had to be quarantined in one day.

The lesson: **reports are not artifacts. Only reruns count.**

## What this is

Three enforcement points + one contract + one config. No dependencies beyond
Python 3.8 standard library.

| Component | File | What it does |
|---|---|---|
| Auditor | `honest_audit.py` | Scans code (comments stripped, C strings included) for forbidden mechanisms from `honesty_patterns.json`. Exit code 1 on BLOCK findings — CI-ready |
| Watcher | `honest_audit_watch.py` | Watches the tree, reports fraud seconds after the file is written |
| Pre-commit gate | `install_precommit.sh` | Blocks `git commit` on BLOCK-severity findings |
| Agent contract | `AGENTS.md` | Drop-in rules any agent reads: claim → saved script → measurement → baseline → verdict |
| Rule config | `honesty_patterns.json` | Your project's invariants as regex categories with `block`/`warn` severity |

Two severity levels, on purpose:

- **BLOCK** — hard fraud, blocks the commit (e.g. backprop in gradient-free code).
- **WARN** — suspicious, judged by a human (e.g. `argmax` is fraud in a selector
  but legal in a measurement harness; `tanh` is fraud in one formula and legal
  in Poincaré geometry). The auditor flags words; **context is judged by humans.**

## 5-minute adaptation to any project

```bash
# 1. copy the package into your repo
cp -r honesty-machine/* your_repo/

# 2. edit the rules — replace the example categories with YOUR invariants
$EDITOR honesty_patterns.json

# 3. install the gate
cd your_repo && bash install_precommit.sh
```

Windows: the hook is a bash script (Git for Windows ships bash); the installer
falls back from `python3` to `python`. Local hooks can always be bypassed with
`git commit --no-verify` — that is why the real gate is CI
(`.github/workflows/ci.yml`), which reruns everything server-side.

An invariant for a web project, for example:

```json
"NETWORK IN TESTS": {
  "severity": "block",
  "why": "tests must be hermetic",
  "patterns": ["\\brequests\\.(get|post)\\b", "\\bhttpx\\b", "\\burllib\\.request\\b"]
}
```

For agents working in your repo, the contract is already there: they read
`AGENTS.md`, and the pre-commit hook does not care what they promise.

## Try it

```bash
$ python3 honest_audit.py examples/
rules: honesty_patterns.json
VERDICT                                       FINDINGS
------------------------------------------------------------------------------------------
FRAUD: BACKPROP / gradient                    examples/fraud_hidden_in_c_string.c
FRAUD: SOFTMAX                                examples/fraud_softmax.py
------------------------------------------------------------------------------------------
clean files: 1, files with findings: 2
FRAUD PRESENT (block-severity categories) — blocking.
```

## Honest limitations (read before trusting)

- **Regex catches words, not meaning.** `softmax` spelled out as `exp/sum/divide`
  under another name evades the gate (see `examples/fraud_softmax.py` note).
  The gate is the first line; the **rerun process** (`docs/METHODOLOGY.md`) is
  what catches semantic fraud. Never rely on the linter alone.
- WARN findings are noisy by design: better a human judges 10 false positives
  than one fraud ships.
- This does not verify your *math* — it verifies that the code matches the claims
  about the code.
- The generated pre-commit hook **excludes `examples/`** (it holds intentional fraud
  for testing the gate). Do not put real project code under `examples/`.
- C++ raw strings `R"(...)"` are not specially parsed. On Python 3.8–3.11,
  expressions inside f-strings are not scanned (fixed in 3.12+ via FSTRING_* tokens).
- The gate itself was audited (2026-11-18) and several bypasses were found and
  fixed — see `docs/FIX_VERDICTS.md`. Audit your gate, too.

## What's inside docs/

- `docs/METHODOLOGY.md` — the full claim→code→measurement→rerun→verdict process,
  including cross-model review (one model builds, another reruns).
- `docs/CASES.md` — the real fraud cases each rule comes from.

## License

MIT — see [LICENSE](LICENSE).
