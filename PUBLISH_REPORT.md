# PUBLISH_REPORT

**Date:** 2026-08-30
**Repository:** **https://github.com/vitalyrodnenko/replay-sim** — public, default branch `main`

Published without rewriting history. No rebase, squash, amend, filter-branch or force
push was used at any point. The push was a **fast-forward**, `8b94d66..bf7b676`, and
`origin/main` was verified to be an ancestor of `main` before it was attempted.

## Pre-push audit

### Secrets scan — **0 hits**

| check | result |
|---|---|
| gitleaks 8.28.0, full history (64 commits, 121.7 MB) | **no leaks found** |
| token/key/password/bearer/`hf_`/`sk-`/`ghp_`/`AKIA`/private-key patterns, all tracked files | no matches |
| `.env`, `*.pem`, `*.key`, `id_rsa`, `credentials`, `.netrc` — tree and history | none, ever |

### Large files — nothing near the limit

**No file exceeds 20 MB**, so nothing was flagged and nothing was moved or deleted.

| size | file |
|---|---|
| 3.95 MB | `results/trace.jsonl` (largest blob in all of history) |
| 3.64 MB × 20 | `results/run9/jitter/trace_J_seed00..19.jsonl` |
| 32 KB | `results/logs/nvidia_smi_calibrate.csv` (largest nvidia-smi dump) |

Total repository ~2.7 MB of source and reports plus ~73 MB of the 20 jitter traces from
run 9's prediction (iv). Those are regenerable from the documented seeds and procedure;
they are kept because the run-9 report cites them, and they are far under any limit.
Flagged here rather than moved, since nothing is deleted or relocated without asking.

### .gitignore

Covers venvs, `__pycache__`, `*.py[cod]`, build artifacts, caches (`.cache/`,
HF/torch-compile), model weights (`*.safetensors`, `*.gguf`, `*.pt`, `*.bin`, `*.onnx`),
editor/local files, and stray top-level nvidia-smi dumps. Verified that **no
already-tracked file becomes ignored**. The nvidia-smi and thermal CSVs under
`results/logs/` and `results/thermal/` remain tracked deliberately — they are the
evidence the reports cite, and a comment in `.gitignore` records that.

### Commit identities — `.mailmap`, not amended

History carries two identities for one person:

| commits | author |
|---|---|
| 31 | `replay-sim <vitaly.rodnenko@gmail.com>` (the early series) |
| 33 | `Vitaly Rodnenko <1169875+vitalyrodnenko@users.noreply.github.com>` |

Per the no-rewrite rule, nothing was amended. A [`.mailmap`](.mailmap) normalises the
display: `git log --format=%aN` now shows 64 commits under one name, while
`git log --format=%an` still returns the original 31/33 split unchanged. Noted in the
README's methodology section.

## Tags

20 tags on the remote: 8 from the first publication (`run1`…`run8a`) and 12 added now,
all annotated, all placed on **existing** commits whose dates are unchanged.

| tag | commit | date | |
|---|---|---|---|
| `run1-v0` | `4bd40d1` | 2026-08-27 | FAIL 1/11 |
| `run2-v0.2` | `fb91d88` | 2026-08-27 | FAIL 9/12 |
| `run3-v0.3` | `266ce75` | 2026-08-27 | FAIL 10/12 |
| `run4-v0.4` | `eef198b` | 2026-08-28 | FAIL 10/12 |
| `run5-v0.5` | `727b81d` | 2026-08-28 | FAIL v2 11/12 |
| `run6-v0.6` | `8130f04` | 2026-08-28 | FAIL v2 5/6 |
| `run7-v0.7` | `4452dce` | 2026-08-28 | FAIL v2 5/6 |
| `run9-v0.8` | `0c9cdf1` | 2026-08-29 | **PASS v2 6/6** |
| `run10-v0.9` | `353f175` | 2026-08-29 | **PASS v2 6/6** |
| `noise-batch` | `92c324d` | 2026-08-29 | 14+14 repeats |
| `ladder` | `72a97b5` | 2026-08-29 | four-point noise curve |
| `load-report` | `eb40435` | 2026-08-29 | validated to 2× |

Run 8a was a diagnostic with no version bump and no verdict; it keeps its original
`run8a` tag and was not given a `-v` name.

## Post-push verification, from outside

Every file fetched over the public raw URL, unauthenticated:

| file | HTTP | bytes |
|---|---|---|
| `README.md` | 200 | 7,582 |
| `PROTOCOL.md` | 200 | 20,194 |
| `LICENSE` | 200 | 11,345 |
| `.mailmap` | 200 | 463 |
| `results/REPORT.md` | 200 | 8,396 |
| `results/REPORT_run1_v0.md` | 200 | 24,670 |
| `results/REPORT_run7_v07.md` | 200 | 13,287 |
| `results/REPORT_run9_v08.md` | 200 | 7,777 |
| `results/REPORT_run10_v09.md` | 200 | 8,396 |

Repository page: HTTP 200. Visibility: public. Tags visible via API: 20.

### Article-facing check 1 — link target resolves

`https://github.com/vitalyrodnenko/replay-sim` returns **HTTP 200** and is public, so
the URL both articles point at resolves for an anonymous reader. Every in-README link
target was checked and resolves.

> **One item is not done.** The README carries **two `[TODO: paste URL]` placeholders**
> where the article links belong, because those URLs were not supplied. A visitor
> arriving from either article will find the repository fine; a visitor wanting to go
> the other way cannot. Paste the two URLs into the "The articles" section and push.

### Article-facing check 2 — the frozen-prediction claim is visible in public history

Verified against the **public GitHub API**, not the local clone. For every run, the
PREDICTIONS commit is both an ancestor of, and authored strictly earlier than, the
results commit that tested it:

| run | PREDICTIONS commit | authored | results commit | authored |
|---|---|---|---|---|
| 1 | `ceb637c` | 2026-08-28T00:21:05Z | `4bd40d1` | 2026-08-28T01:57:44Z |
| 1 (corrected) | `4a454c1` | 2026-08-28T01:37:25Z | `4bd40d1` | 2026-08-28T01:57:44Z |
| 2 | `43fe037` | 2026-08-28T03:30:41Z | `fb91d88` | 2026-08-28T03:57:22Z |
| 3 | `e28649b` | 2026-08-28T04:20:31Z | `266ce75` | 2026-08-28T04:51:25Z |
| 4 | `8a4a02e` | 2026-08-28T12:27:36Z | `eef198b` | 2026-08-28T12:31:34Z |
| 5 | `ece387b` | 2026-08-28T13:10:27Z | `3cb8a91` | 2026-08-28T13:24:11Z |
| 6 | `2dfd58a` | 2026-08-28T13:46:45Z | `8130f04` | 2026-08-28T13:52:31Z |
| 7 | `2714147` | 2026-08-28T14:21:02Z | `4452dce` | 2026-08-28T14:26:49Z |
| 9 | `3973a6a` | 2026-08-29T20:34:18Z | `0c9cdf1` | 2026-08-29T20:40:23Z |
| 10 | `6cd41c0` | 2026-08-29T20:51:48Z | `353f175` | 2026-08-29T20:56:34Z |

**All 10 pairs: ancestor and earlier. The claim the articles make is checkable by any
reader from the public history alone.**

## Upstream issue

Filed from `results/vllm_issue_draft.md`, updated to link the public
`BOOT_MATRIX.md`, the four boot-matrix CSVs and the per-boot server logs as
reproduction data:

> **https://github.com/vllm-project/vllm/issues/54383** — OPEN
> *First boot of a new `(max-num-batched-tokens, max-num-seqs)` shape is granted a ~5%
> smaller KV cache than subsequent identical boots*

## Changes made in this publication

- `README.md` rewritten as a visitor front door. **No content was deleted**: the full
  internal protocol log moved verbatim to `PROTOCOL.md` (402 lines, byte-identical,
  all six VERDICT CRITERION v2 sections and all five run protocols intact).
- `LICENSE` changed from **MIT to Apache-2.0**, copyright 2026 Vitaly Rodnenko. This
  relicenses material that was already published under MIT in the first push.
- `.mailmap` added; `.gitignore` extended.
