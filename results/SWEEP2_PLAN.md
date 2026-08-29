# SWEEP2_PLAN — pre-registration

**Written and committed 2026-08-29, before the sweep was run.**
**v0.7 and run-5 `perf.json` stay installed and untouched. No verdict change.**
**The v0.8 archive is not installed and must not contaminate this sweep.**

> ## Scope, and it is the point of this document
> **Every claim produced by this sweep is scoped to ≤ 2× arrival rate.**
> `results/LOAD_REPORT.md` validated the cost model against real runs at 1.5× and 2×,
> where every cost row passed with delta gaps ≤ 0.7 points. At 3× it failed —
> `throughput_tok_s` gap 15.4 points against a 15-point bar — and it failed
> *optimistically*, predicting +113.6% throughput where the server delivered +98.2%.
> **3× and beyond is out of scope pending the saturation fix.** No row in this sweep
> extrapolates past 2×, and none may be quoted as if it did.

## 1. Grid

util {0.70, 0.75, 0.78, 0.82, 0.85, 0.88} × mns {64, 128} × mbt {2048, 8192},
prefix caching on = **24 configs**, each simulated at speedups {1, 1.5, 2} using the
committed scaled traces (`trace.jsonl`, `trace_s15.jsonl`, `trace_s2.jsonl`).

**= 72 simulations.** The brief says 120; that is the count from last night's sweep,
which ran five speedups. The grid specified here has three, so 24 × 3 = 72. The grid
as written is what runs.

v0.7 simulator, run-5 `perf.json`, `--drop-first 10`, pool per config from
`results/pool_model.json`.

## 2. Objective

A config **survives** a speedup when its predicted `e2e_p95` at that speedup is within
**1.10 ×** the **measured** config-A `e2e_p95` at the *same* speedup. Each config's
capacity is the highest speedup in {1, 1.5, 2} it survives. Ranked by survivable
speedup, then by `gpu_s_per_1k_out_tok` at that speedup.

Anchoring the guard to measured rather than predicted values is the correction
`LOADSWEEP_PROVISIONAL.md` flagged: predicted `e2e_p95` ran 3–15% below measured on
every real run, so a predicted anchor sets the bar too low.

### Anchors

| speedup | anchor as briefed | source | anchor used in sensitivity |
|---|---|---|---|
| 1× | **7.793 s** | `results/real_A_v0_run1.json` — config A in **run 1** | 7.543 s |
| 1.5× | **11.625 s** | `results/load/real_A_s15.json`, this week | — |
| 2× | **24.900 s** | `results/load/real_A_s2.json`, this week | — |

**The 1× anchor is from a different measurement epoch.** 7.793 s is config A's
`e2e_p95` from run 1 on 2026-08-27, under the v0 simulator era and before the
strict-drain/asserted-pool protocol existed. The 1.5× and 2× anchors are from this
week's load runs. Config A's `e2e_p95` measured **now** is 7.534 s (`real_A.json`) and
**7.543 s ± 0.015** over the 14 clean repeats of the noise batch.

Using 7.793 makes the 1× guard 8.572 s instead of 8.297 s — **3.3% more permissive**,
which can only ever promote a config from "fails at 1×" to "survives 1×", never demote
one.

Both are run. **Primary = the briefed anchors, unchanged.** A sensitivity column uses
7.543 s at 1×, and the report states every config whose capacity differs between them.

## 3. GPU validation

The top-2 candidates and the default, one real run each **at 2×** — the binding
speedup and the top of the validated envelope. Standard protocol: strict VRAM drain,
asserted 87,200-token pool, `/health` gate, `--drop-first 10`, `--per-request`.

**These are single runs.** `NOISE_REPORT.md` and `LADDER_REPORT.md` set the error bars:
at config A, `throughput_tok_s` CV is 0.02% and `e2e_p95` CV 0.19% over 14 repeats, so
differences of a few tenths of a percent in those metrics are resolvable from one run;
`ttft_p95` is not (CV 0.69% at A, 6.07% at J, and bimodal at J), and no `ttft_p95`
conclusion will be drawn from a single run.

## 4. What this sweep will not do

No simulator change, no `perf.json` change, no verdict-criterion change, no
re-scoring, no outlier rejection, no claim above 2×, and no installation of v0.8.

## 5. Deliverables

- `results/SWEEP2_REPORT.md` — capacity table, default's position, best config's
  edge over the default, and the predicted-vs-measured section from §3.
- `results/sweep2/sweep2.json` and the individual `sim_*.json`.
