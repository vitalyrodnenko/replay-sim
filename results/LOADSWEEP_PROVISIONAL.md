> # PROVISIONAL: valid only if LOAD_REPORT.md answers yes; guard thresholds must be re-anchored to measured baselines before any external use.

> ## ⚠ LOAD_REPORT.md answers **NO**.

> The cost model failed its held-out load validation — 15.4 points. **Every number below is therefore unusable as a capacity claim.** It is published because the sweep was specified and the grid is worth keeping, not because it can be acted on. See §0.


# LOADSWEEP_PROVISIONAL — capacity ranking on the cost model

**Date:** 2026-08-29  
**No simulator, `perf.json`, or verdict change.** Simulated throughout: no config below was run for real at any speedup.

## 0. Why this is not actionable

`LOAD_REPORT.md` put the same simulator against real runs at 1.5×, 2× and 3× and it failed the pre-registered rule: 15.4 points. Worse for this document specifically, it failed **in the optimistic direction** — at 3× the model predicted throughput rising +113.6% where the server delivered +98.2%, so it under-models saturation. A capacity table built on it will overstate how much load each config survives, which is exactly the error that matters here.

The validated range is **up to 2×**, where every cost row passed with gaps of 0.7 points or less. Rows at 3× and 4× below are extrapolation past the point where the model is known to break.

A second, independent reason: the SLO guard is `1.10 ×` config A's **predicted** `e2e_p95` at the same speedup. Predicted `e2e_p95` ran 3–15% below measured on every real run in `LOAD_REPORT.md`, so these guards sit below the real ones and admit configs a measured guard would reject.

## 1. Method

util {0.70, 0.75, 0.78, 0.82, 0.85, 0.88} × mns {64, 128} × mbt {2048, 8192}, prefix caching on = 24 configs, each simulated at speedups {1, 1.5, 2, 3, 4} via the scaled traces = **120 sims**, v0.7 + run-5 `perf.json`, `--drop-first 10`.

A config **survives** a speedup if its predicted `e2e_p95` at that speedup is within 1.10× of config A's predicted `e2e_p95` **at the same speedup** — the anchor moves with the load, so this measures relative resilience, not absolute latency.

| speedup | config-A anchor `e2e_p95` | guard (1.10×) |
|---|---|---|
| 1× | 6.795 s | 7.475 s |
| 1.5× | 11.268 s | 12.395 s |
| 2× | 21.274 s | 23.401 s |
| 3× | 45.913 s | 50.504 s |
| 4× | 50.925 s | 56.017 s |

## 2. Capacity table

| rank | util | mns | mbt | blocks | max survivable speedup | `gpu_s_per_1k` at cap |
|---|---|---|---|---|---|---|
| 1 | 0.88 | 128 | 2048 | 5,811 | **≥4×** | 2.185 |
| 2 | 0.88 | 128 | 8192 | 5,502 | **≥4×** | 2.196 |
| 3 | 0.88 | 64 | 2048 | 5,841 | **≥4×** | 2.210 |
| 4 | 0.88 | 64 | 8192 | 5,532 | **≥4×** | 2.210 |
| 5 | 0.85 | 64 | 2048 | 5,479 | **≥4×** | 2.258 |
| 6 | 0.85 | 128 | 2048 | 5,449 | **≥4×** | 2.274 ← **default (A)** |
| 7 | 0.85 | 64 | 8192 | 5,170 | **≥4×** | 2.310 |
| 8 | 0.85 | 128 | 8192 | 5,140 | **≥4×** | 2.395 |
| 9 | 0.82 | 64 | 2048 | 5,118 | **≥4×** | 2.396 |
| 10 | 0.82 | 128 | 2048 | 5,088 | **≥4×** | 2.505 |
| 11 | 0.82 | 128 | 8192 | 4,779 | **≥4×** | 2.542 |
| 12 | 0.82 | 64 | 8192 | 4,809 | **≥4×** | 2.547 |
| 13 | 0.78 | 64 | 2048 | 4,637 | **≥4×** | 2.617 |
| 14 | 0.78 | 128 | 2048 | 4,607 | **≥4×** | 2.724 |
| 15 | 0.78 | 128 | 8192 | 4,298 | **≥4×** | 2.787 |
| 16 | 0.75 | 128 | 2048 | 4,245 | 3× | 2.833 |
| 17 | 0.75 | 64 | 2048 | 4,275 | 3× | 2.836 |
| 18 | 0.78 | 64 | 8192 | 4,328 | 3× | 2.916 |
| 19 | 0.70 | 64 | 2048 | 3,673 | **fails at 1×** | — |
| 20 | 0.70 | 64 | 8192 | 3,364 | **fails at 1×** | — |
| 21 | 0.70 | 128 | 2048 | 3,643 | **fails at 1×** | — |
| 22 | 0.70 | 128 | 8192 | 3,334 | **fails at 1×** | — |
| 23 | 0.75 | 64 | 8192 | 3,966 | **fails at 1×** | — |
| 24 | 0.75 | 128 | 8192 | 3,936 | **fails at 1×** | — |

## 3. What the table does and does not say

**The capacity metric is right-censored.** 15 of 24 configs survive 4×, the largest speedup tested, so their true capacity is `≥4×` and unknown. The ranking among them is decided entirely by the tie-break — `gpu_s_per_1k` at 4× — not by capacity at all. Extending the axis past 4× would be needed to separate them, and per §0 that is well beyond where the model is trustworthy.

**6 configs fail at 1×**, all of them util 0.70, or util 0.75 with mbt 8192. Their predicted `e2e_p95` at baseline load is 11–22 s against a 7.47 s guard: the pool is small enough that eviction dominates before any extra load is applied.

**The default's position: rank 6 of 24**, surviving `≥4×` with `gpu_s_per_1k` = 2.274 at 4×.

**Best config's headroom over the default: 3.91%** — util 0.88, mns 128, mbt 2048 at 2.185 vs 2.274 `gpu_s_per_1k` at 4×, both censored at the same survivable speedup. That 3.91% is a difference between two simulated numbers from a model that just failed its load validation; it is not a saving anyone should plan against.

## 4. Was Task 1 cut short?

No. All three scaled traces were predicted, frozen, committed and run for real with the full protocol, and every boot asserted the 87,200-token pool. The session finished measurement well inside its budget. The `no` in `LOAD_REPORT.md` is a result, not a truncation.

