# SWEEP_REPORT — config sweep on the validated cost model

**Date:** 2026-08-29  
**Simulator:** v0.7 as installed in run 7, unmodified. **`perf.json`:** run-5, unmodified.  
**Trace:** `results/trace.jsonl`, the same 192 requests every run in the series used.  
**No physics change, no calibration change, no verdict.**

## What is being asked

For each of the 256 configurations below, what does the simulator predict it would cost to serve this workload, and which of them stay inside an SLO guard derived from the current default?

- **Objective:** minimise `gpu_s_per_1k_out_tok`.
- **SLO guard:** predicted `e2e_p95` ≤ 1.10 × config A = **7.475 s**.
- **Grid:** util × mns × mbt × prefix-caching = **256 configs**, of which **36** clear the guard.

## How much each number is worth

This matters more than the ranking, so it goes first.

- **The objective is the part the series actually validated.** Across runs 3–7 every held-out cost row passed: `throughput_tok_s` and `prefix_cache_hit_rate` gaps never exceeded the 15-point bar on any held-out config. `gpu_s_per_1k_out_tok` is derived from the same `gpu_busy_s` accounting.
- **The SLO guard is weaker.** `e2e_p95` carried a mean absolute error near 6% in-sample. A config sitting within a few percent of the guard could be on either side of it in reality.
- **`ttft_p95` is reported but must not be trusted for ranking.** It is the one metric that has failed on every held-out config since run 3, and run 7 measured it over-predicting by +52.9% (F), +32.5% (J) and +37.0% (K) in the pool-pressure zone — exactly where the cheap candidates below sit.
- **Pool sizes are modelled, and the pool is not boot-reproducible.** Booting identical settings twice gave 82,656 and 87,680 tokens (`results/NOISE_PLAN.md`, amendment). Levels marked SINGLE/ESTIMATED below rest on one boot each.

### Pool model

`tokens = base(util) + off_mbt[mbt] + off_mns[mns]`, base fitted on 8 reference-shape points (collinear to within 4 tokens).

| axis | level | offset (tokens) | confidence | provenance |
|---|---|---|---|---|
| mbt | 1024 | -4,944 | SINGLE | p_mbt1024 tonight, one boot |
| mbt | 2048 | +0 | CONFIRMED | reference shape, booted dozens of times in the series |
| mbt | 4096 | -5,184 | SINGLE | p_mbt4096 tonight, one boot |
| mbt | 8192 | -4,944 | CONFIRMED | G at util 0.85 (-4,944) and I at util 0.78 (-4,947), agree to 3 tokens |
| mns | 16 | +700 | ESTIMATED | no clean measurement; extrapolated from 32:+640, 64:+480, 128:0 |
| mns | 32 | +640 | PUBLISHED | config D, run 2 |
| mns | 64 | +480 | SINGLE | p_repeat_mns64 (87,680); the earlier p_mns64 boot gave 82,656 |
| mns | 128 | +0 | CONFIRMED | reference shape |

## Top 10 feasible configs

| # | config | blocks | gpu_s/1k | vs A | e2e_p95 | ttft_p95 | tok/s | hit |
|---|---|---|---|---|---|---|---|---|
| 1 | util 0.88 · mns  16 · mbt 2048 · pc on | 5,854 | 4.575 | -0.57% | 6.557 | 0.652 | 209.4 | 0.862 |
| 2 | util 0.88 · mns  32 · mbt 2048 · pc on | 5,851 | 4.575 | -0.57% | 6.557 | 0.652 | 209.4 | 0.862 |
| 3 | util 0.88 · mns  16 · mbt 8192 · pc on | 5,545 | 4.575 | -0.57% | 6.557 | 0.652 | 209.4 | 0.862 |
| 4 | util 0.88 · mns  64 · mbt 2048 · pc on | 5,841 | 4.575 | -0.57% | 6.557 | 0.652 | 209.4 | 0.862 |
| 5 | util 0.88 · mns 128 · mbt 2048 · pc on | 5,811 | 4.575 | -0.57% | 6.557 | 0.652 | 209.4 | 0.862 |
| 6 | util 0.88 · mns  16 · mbt 1024 · pc on | 5,545 | 4.576 | -0.54% | 6.557 | 0.652 | 209.4 | 0.862 |
| 7 | util 0.88 · mns  16 · mbt 4096 · pc on | 5,530 | 4.576 | -0.54% | 6.557 | 0.652 | 209.3 | 0.862 |
| 8 | util 0.88 · mns  32 · mbt 1024 · pc on | 5,542 | 4.576 | -0.54% | 6.557 | 0.652 | 209.4 | 0.862 |
| 9 | util 0.88 · mns  32 · mbt 8192 · pc on | 5,542 | 4.576 | -0.54% | 6.557 | 0.652 | 209.4 | 0.862 |
| 10 | util 0.88 · mns  64 · mbt 8192 · pc on | 5,532 | 4.576 | -0.54% | 6.557 | 0.652 | 209.3 | 0.862 |

## Where the default sits

Config A — util 0.85 · mns 128 · mbt 2048 · pc on — ranks **20 of 36** feasible configs, at `gpu_s_per_1k_out_tok` = 4.601.

## Headline

> **Predicted cost-per-task saving of the best feasible config over the current default: 0.57%.**

Best: util 0.88 · mns  16 · mbt 2048 · pc on (5,854 blocks), `gpu_s_per_1k_out_tok` 4.575 vs 4.601, with predicted `e2e_p95` 6.557 s against a 7.475 s guard.

## Robustness to the pool irreproducibility

The whole sweep was re-run with every SINGLE/ESTIMATED pool level raised by 5,024 tokens — the size of the observed boot-to-boot spread — to see whether the ranking survives it.

- feasible configs: 36 → 46
- best config: `u0.88_s16_b2048_on` → `u0.85_s16_b1024_on`  (**changed**)
- headline saving: 0.57% → 0.57%
- top-10 membership overlap: **4/10**

**Which config wins is not robust; what it wins by is.** The identity of the best config changes and only 4 of the top 10 survive, because those configs are separated by less than the pool uncertainty. But the headline saving is unchanged at 0.57%, and the default's position barely moves (20 of 36 → 30 of 46). The conclusion of this sweep does not rest on the pool numbers being exact.

## How flat the frontier is — the real result

The 36 feasible configs span **4.575 to 4.695** `gpu_s_per_1k_out_tok`, a total spread of **2.6%**. Across all 256 configs the range is 4.575–10.958 (2.4×), but every config materially cheaper than the default is one the SLO guard rejects, and the expensive tail is all small pools and caching-off.

**The top of the ranking is a plateau, not an optimum.** 5 configs tie at the best cost to within 0.0005; they differ only in `mns` and `mbt`, which stop mattering once the pool is large enough that nothing is evicted. Choosing among them on this model is arbitrary.

So the honest reading of this sweep is a **negative result**: on this workload, under this SLO guard, the current default is already within 0.57% of the best configuration the cost model can find. There is no meaningful cost win available by reconfiguring; the win, if one exists, is in a bigger KV pool, and utilisation is already near the boot ceiling (0.90 and 0.93 both fail CUDA-graph capture on this box).

## Cross-check against the frozen published simulations

Three grid points are configs the series already ran: rank 5 is **H**, rank 20 is **A** (the default), rank 36 is **J**. Their sweep rows should reproduce the frozen `sim_*_v07_run7.json` files, and they do:

| config | rank | sweep blocks | published blocks | agreement |
|---|---|---|---|---|
| H | 5 | 5,811 | 5,811 | **exact on all 7 metrics** |
| A | 20 | 5,449 | 5,450 | 1 block apart; throughput 208.2 vs 208.3 |
| J | 36 | 5,088 | 5,089 | 1 block apart; e2e_p95 7.434 vs 7.427 |

The one-block gaps are the pool model rounding, and they move no metric by more than 0.09%. The sweep is running the same simulator the series froze.

## Predicted vs measured — exploratory real runs

The top two feasible configs and one mid-ranked control were run for real, once each, with the standard protocol (fresh server, strict VRAM drain, `--drop-first 10`). **These are single runs.** Task 1 measured what a single run is worth on this workload, and that is what makes them readable at all.

| config | metric | predicted | measured | error |
|---|---|---|---|---|
| top1 (rank 1) | `ttft_p50_s` | 0.227 | 0.248 | -8.5% |
| top1 (rank 1) | `ttft_p95_s` | 0.652 | 0.559 | +16.6% |
| top1 (rank 1) | `e2e_p50_s` | 4.494 | 4.762 | -5.6% |
| top1 (rank 1) | `e2e_p95_s` | 6.557 | 7.217 | -9.1% |
| top1 (rank 1) | `throughput_tok_s` | 209.400 | 209.200 | +0.1% |
| top1 (rank 1) | `prefix_cache_hit_rate` | 0.862 | 0.862 | +0.0% |
| top2 (rank 2) | `ttft_p50_s` | 0.227 | 0.247 | -8.1% |
| top2 (rank 2) | `ttft_p95_s` | 0.652 | 0.536 | +21.6% |
| top2 (rank 2) | `e2e_p50_s` | 4.494 | 4.754 | -5.5% |
| top2 (rank 2) | `e2e_p95_s` | 6.557 | 7.205 | -9.0% |
| top2 (rank 2) | `throughput_tok_s` | 209.400 | 209.200 | +0.1% |
| top2 (rank 2) | `prefix_cache_hit_rate` | 0.862 | 0.862 | +0.0% |
| ctrl (rank 21 control) | `ttft_p50_s` | 0.231 | 0.250 | -7.6% |
| ctrl (rank 21 control) | `ttft_p95_s` | 0.929 | 0.799 | +16.3% |
| ctrl (rank 21 control) | `e2e_p50_s` | 4.614 | 4.848 | -4.8% |
| ctrl (rank 21 control) | `e2e_p95_s` | 7.252 | 7.900 | -8.2% |
| ctrl (rank 21 control) | `throughput_tok_s` | 205.100 | 204.500 | +0.3% |
| ctrl (rank 21 control) | `prefix_cache_hit_rate` | 0.845 | 0.844 | +0.1% |

### What the real runs settle

**The ranking holds.** Predicted order was top1 ≈ top2 cheaper than the default, control more expensive. Measured throughput: top1 209.2, top2 209.2, default 207.7, control 204.5 tok/s — exactly that order.

**And the difference is resolvable.** Config A's throughput over Task 1's 14 repeats is 207.72 tok/s with a CV of 0.020%, so its 95% noise band is ±0.04%. The top configs beat that mean by +0.71% — about 18× the band. A 0.57% predicted saving sounds like nothing, but on this benchmark throughput is measured tightly enough that it is a real, repeatable difference.

**The cost metrics predict well; the SLO guard does not.** Throughput and hit rate came in within +0.3% on all three configs. But `e2e_p95` was **under-predicted by 8–9% on every one**, and `ttft_p95` over-predicted by +16% to +22% — the same defect the series has carried since run 3.

> **The guard used in this report is therefore optimistic.** It was set at 1.10 × the *simulated* config-A `e2e_p95` = 7.475 s. Measured against Task 1's 14-run mean for A the guard should be 8.297 s. A config predicted to sit just inside the guard could breach it in reality; all three configs run here stayed within the measured guard, but that is luck, not margin.

**The pool model held up on real boots.** Predicted vs granted: top2 exact, top1 −48 tokens (−0.05%), control −620 (−0.75%). The control combines a CONFIRMED `mbt` offset with an ESTIMATED `mns` one, which is where the additive assumption is weakest. None of the three showed anything like the 5,024-token boot-to-boot spread — with the strict drain in place, the pool was what the model said it would be.

## Full ranking

All 256 configs with their predictions are in `results/sweep/sweep_results.json`; each individual simulator output is in `results/sweep/sim_<tag>.json`.

