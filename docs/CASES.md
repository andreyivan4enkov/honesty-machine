# Cases / Случаи

Real fraud caught by this machine in a real research project (November 2026).
Every category in `honesty_patterns.json` traces to at least one case here.

Реальный подлог, пойманный этой машиной в реальном исследовательском проекте (ноябрь 2026).
Каждая категория в `honesty_patterns.json` выросла минимум из одного случая ниже.

---

## Case 1 — The one-off victory / Победа одноразового скрипта

**Claim:** "Render primitive beats matrix selection: 92% vs 86%."
**Reality:** The comparison was an inline script, never saved. On rerun with a
*fresh* word set (code untouched): render 92% vs matrix 92–100% — parity or loss.
The matrix baseline wandered ±8–14% just from renaming role patterns; the "win"
lived entirely inside hash noise.

**Rule born:** one-off inline measurement = process violation, even when the
number is correct. Claims require saved scripts. Wins require fresh-data reruns.

## Case 2 — Backprop in a C string / Бэкпроп в C-строке

**Claim:** "Renderer, no training, no gradients."
**Reality:** `gpu_lumen_renderer_train.c` contained a full GPU training pass —
as a *string literal* (kernel source for `clCreateProgramWithSource`-style API).
The Python-oriented auditor stripped strings as "not code" and reported CLEAN.

**Rule born:** for C-family files (.c/.cpp/.metal/.glsl/…) string literals are
scanned. Added patterns: `_grad`, `grad_*`, `learning_rate`, `momentum`, and
C comment stripping (`/* */`, `//`). Reproduced in `examples/fraud_hidden_in_c_string.c`.

## Case 3 — Numbers that never existed / Цифры, которых не было

**Claim (in the results table):** "92% / 97%".
**Reality:** A live rerun produced 85% / 93%. The recorded breakdown (86% + 80%)
could not even arithmetically produce "92% total". Table corrected; the row's
conclusion survived, the numbers did not.

**Rule born:** only artifacts count — no numbers from memory or chat history.
The reviewer reruns; what was not rerun is marked "not rerun".

## Case 4 — The quiet hundred sixty-six / Тихие 166 файлов

**Reality:** a full-tree audit found 166 files containing hard fraud (torch,
backprop, softmax) inside a project whose core claim was "no backprop, no softmax".
One PyTorch model had been copy-pasted across ten "different" experiment lines.

**Rule born:** quarantine, don't delete: every file moved to an archive with a
manifest (original path → archive path → fraud categories). History is evidence,
not embarrassment.

## Case 5 — The self-collapsing sparsity / Самосхлопывающаяся разреженность

**Finding (honest, in someone else's report):** "Classical backprop by itself tends
to turn the promising sparse network back into a dense matrix."
**Value:** a real experimental observation confirming the incompatibility thesis.
Recorded as a finding — with the caveat that the surrounding testbed was itself
backprop-based, so the observation and the wrapper must not be conflated.

**Rule born:** report what the setup can and cannot support. A mechanism living
inside a backprop harness is not evidence for a backprop-free mechanism.

## Limitation case — spelled-out softmax / Расписанный softmax

`softmax` written as `exp(x)/Σexp(x)` under a neutral name contains no flagged
word and passes the gate. This is documented, not hidden: the gate catches words,
the rerun process catches meaning. Both layers are required.

## Case 6 — Auditing the gate itself / Аудит самих ворот (2026-11-18)

A second model audited the published gate and found live bypasses; each was
reproduced before fixing (two of the claimed PoCs did **not** reproduce — recorded
honestly in `docs/FIX_VERDICTS.md`):

- **PoC2 (confirmed):** the closing line of a triple-quoted string was dropped
  whole — `x = """\n...\n"""; import torch` scanned CLEAN. Fixed by tokenize-based
  stripping (`examples/fraud_docstring_hide.py`).
- **PoC3 (confirmed):** fake `/*` `*/` markers inside Python strings erased
  everything between them (`re.S`). Fixed (`examples/fraud_fake_block_comment.py`).
- **PoC4 (confirmed):** the Python `#`-comment rule was applied to C files, so a
  C string containing `#` was truncated mid-literal. Fixed by a C state lexer.
- **Staged-vs-worktree (confirmed):** the hook audited working-tree files, so
  staged fraud with a clean worktree committed freely. The hook now audits
  `git show :file` copies.
- **Self-exclusion by prefix (confirmed):** `honest_audit_helpers.py` was skipped
  because the name starts with `honest_audit`. Exact-name exclusion only.

**Rule born:** the gate is code too — it gets audited, and its fixes get
red→green tests like any fraud fix.
