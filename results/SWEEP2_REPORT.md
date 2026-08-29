> # Scope: every claim here is valid to ≤ 2× arrival rate only.

> `LOAD_REPORT.md` validated this cost model against real runs at 1.5× and 2× (all cost rows passing, gaps ≤ 0.7 pt) and it **failed at 3×** — `throughput_tok_s` gap 15.4 points against a 15-point bar — failing *optimistically*. **3× and beyond is out of scope pending the saturation fix.**


# SWEEP2_REPORT — capacity inside the validated envelope

**Date:** 2026-08-29  
**Pre-registered** in `results/SWEEP2_PLAN.md`.  
**v0.7 and run-5 `perf.json` installed and untouched; v0.8 not installed.**

24 configs × 3 speedups = **72 simulations**. (The brief said 120; that is last night's count with five speedups. Three speedups over this grid is 72.)

## Guards

Anchored to **measured** config-A `e2e_p95` at the same speedup — the correction `LOADSWEEP_PROVISIONAL.md` flagged, since predicted `e2e_p95` ran 3–15% below measured on every real run.

| speedup | anchor | guard (1.10×) | source |
|---|---|---|---|
| 1× | 7.793 s | 8.572 s | `real_A_v0_run1.json` — **run 1, a different epoch** |
| 1.5× | 11.625 s | 12.788 s | `load/real_A_s15.json`, this week |
| 2× | 24.900 s | 27.390 s | `load/real_A_s2.json`, this week |

**The 1× anchor as briefed is stale.** 7.793 s is config A from run 1, before the strict-drain and asserted-pool protocol existed; A measures 7.534 s now, or 7.543 ± 0.015 over the noise batch's 14 repeats. That makes the 1× guard 3.3% more permissive. The sweep was run both ways and **0 configs change capacity** — the stale anchor makes no difference to any result below, because no config in this grid has its capacity decided at 1×.

## Capacity table

| rank | util | mns | mbt | blocks | max survivable speedup | `gpu_s_per_1k` at cap | predicted `e2e_p95` @2× |
|---|---|---|---|---|---|---|---|
| 1 | 0.88 | 64 | 2048 | 5,841 | **≥2×** | 2.480 | 21.274 s |
| 2 | 0.88 | 128 | 2048 | 5,811 | **≥2×** | 2.480 | 21.274 s |
| 3 | 0.88 | 64 | 8192 | 5,532 | **≥2×** | 2.496 | 21.273 s |
| 4 | 0.88 | 128 | 8192 | 5,502 | **≥2×** | 2.506 | 21.273 s |
| 5 | 0.85 | 64 | 2048 | 5,479 | **≥2×** | 2.512 | 21.274 s |
| 6 | 0.85 | 128 | 2048 | 5,449 | **≥2×** | 2.524 | 21.274 s | ← **default (A)**
| 7 | 0.85 | 64 | 8192 | 5,170 | **≥2×** | 2.590 | 21.273 s |
| 8 | 0.85 | 128 | 8192 | 5,140 | **≥2×** | 2.601 | 21.273 s |
| 9 | 0.82 | 64 | 2048 | 5,118 | **≥2×** | 2.611 | 21.274 s |
| 10 | 0.82 | 128 | 2048 | 5,088 | **≥2×** | 2.624 | 21.369 s |
| 11 | 0.82 | 64 | 8192 | 4,809 | **≥2×** | 2.683 | 22.940 s |
| 12 | 0.78 | 64 | 2048 | 4,637 | **≥2×** | 2.761 | 24.536 s |
| 13 | 0.82 | 128 | 8192 | 4,779 | **≥2×** | 2.781 | 26.386 s |
| 14 | 0.78 | 128 | 2048 | 4,607 | **≥2×** | 2.836 | 26.013 s |
| 15 | 0.70 | 64 | 2048 | 3,673 | **fails at 1×** | — | 38.770 s |
| 16 | 0.70 | 64 | 8192 | 3,364 | **fails at 1×** | — | 56.747 s |
| 17 | 0.70 | 128 | 2048 | 3,643 | **fails at 1×** | — | 41.166 s |
| 18 | 0.70 | 128 | 8192 | 3,334 | **fails at 1×** | — | 58.037 s |
| 19 | 0.75 | 64 | 2048 | 4,275 | **fails at 1×** | — | 28.216 s |
| 20 | 0.75 | 64 | 8192 | 3,966 | **fails at 1×** | — | 39.062 s |
| 21 | 0.75 | 128 | 2048 | 4,245 | **fails at 1×** | — | 32.799 s |
| 22 | 0.75 | 128 | 8192 | 3,936 | **fails at 1×** | — | 36.705 s |
| 23 | 0.78 | 64 | 8192 | 4,328 | **fails at 1×** | — | 29.964 s |
| 24 | 0.78 | 128 | 8192 | 4,298 | **fails at 1×** | — | 28.074 s |

## What the table says

**There is no survivable-load edge. 14 of 24 configs survive 2×**, the top of the validated envelope, so their capacity is `≥2×` and censored — the true ceiling is unknown and cannot be probed without leaving the envelope. The best config and the default both reach 2×, so the edge in survivable load is **0%**.

The ranking among those 14 is decided entirely by the tie-break, `gpu_s_per_1k` at 2×. On that: **best beats default by 1.74%** (util 0.88 / mns 64 / mbt 2048 at 2.480 vs 2.524). Predicted `e2e_p95` at 2× is 21.274 s for the top nine configs — indistinguishable — so the guard separates nothing up there either.

**The default's position: rank 6 of 24.** The five configs above it are all util 0.88 or util 0.85 with mns 64; the gain is pool size, and utilisation is already near this box's boot ceiling (0.90 and 0.93 both fail CUDA-graph capture).

**10 configs fail at 1×** — every util 0.70 and 0.75 config, plus util 0.78 with mbt 8192. Their predicted `e2e_p95` at baseline load already exceeds the 1× guard, so they never enter the ranking.

## Predicted vs measured at 2× (GPU validation)

One real run each, at 2× — the binding speedup and the top of the validated envelope. Standard protocol: strict drain, asserted pool, `--drop-first 10`.

| config | metric | predicted | measured | error |
|---|---|---|---|---|
| top1 (rank 1) | `ttft_p50_s` | 0.391 | 0.425 | -8.0% |
| top1 (rank 1) | `ttft_p95_s` | 1.591 | 1.077 | +47.7% |
| top1 (rank 1) | `e2e_p50_s` | 12.231 | 13.836 | -11.6% |
| top1 (rank 1) | `e2e_p95_s` | 21.274 | 24.985 | -14.9% |
| top1 (rank 1) | `throughput_tok_s` | 402.000 | 398.300 | +0.9% |
| top1 (rank 1) | `prefix_cache_hit_rate` | 0.862 | 0.862 | +0.0% |
| top2 (rank 2) | `ttft_p50_s` | 0.391 | 0.426 | -8.2% |
| top2 (rank 2) | `ttft_p95_s` | 1.591 | 1.072 | +48.4% |
| top2 (rank 2) | `e2e_p50_s` | 12.231 | 13.859 | -11.7% |
| top2 (rank 2) | `e2e_p95_s` | 21.274 | 25.045 | -15.1% |
| top2 (rank 2) | `throughput_tok_s` | 402.000 | 398.300 | +0.9% |
| top2 (rank 2) | `prefix_cache_hit_rate` | 0.862 | 0.862 | +0.0% |
| dflt (rank 6) | `ttft_p50_s` | 0.407 | 0.439 | -7.3% |
| dflt (rank 6) | `ttft_p95_s` | 1.649 | 1.534 | +7.5% |
| dflt (rank 6) | `e2e_p50_s` | 12.599 | 14.690 | -14.2% |
| dflt (rank 6) | `e2e_p95_s` | 21.274 | 25.293 | -15.9% |
| dflt (rank 6) | `throughput_tok_s` | 395.100 | 391.900 | +0.8% |
| dflt (rank 6) | `prefix_cache_hit_rate` | 0.857 | 0.857 | +0.0% |

### Did the ranking hold?

Throughput is the low-noise cost proxy — CV 0.02% over config A's 14 repeats, so a 95% noise band of ±0.04%. Ranked by measured throughput:

| measured rank | config | throughput | vs default |
|---|---|---|---|
| 1 | top1 (predicted rank 1) | 398.3 tok/s | +1.63% |
| 2 | top2 (predicted rank 2) | 398.3 tok/s | +1.63% |
| 3 | dflt (predicted rank 6) | 391.9 tok/s | +0.00% |

**The predicted ordering held.** The model put top1 and top2 at an exact tie (2.480 `gpu_s_per_1k` each, identical predicted `e2e_p95`) and ahead of the default, and that is what came back: they measured identically at 398.3 tok/s, both above the default's 391.9. `max_num_seqs` 64 vs 128 changed nothing measurable at this load, exactly as predicted.

**Edge over the default: predicted 1.74% on cost, measured +1.63% on throughput.** Both are far outside throughput's ±0.04% noise band, so the difference is real — it is simply small.

### Where the model is still wrong

`throughput_tok_s` and `prefix_cache_hit_rate` came in within +0.9% on all three configs. `e2e_p95` was **under-predicted by 14.9–15.9% on every one** — the same optimistic bias every load run has shown. `ttft_p95` was over-predicted by +47.7% and +48.4% on the two util-0.88 configs against +7.5% on the default; per the plan no `ttft_p95` conclusion is drawn from single runs, but the size of that gap is worth recording.

**One observation about the guard itself.** The 2× anchor is 24.900 s, measured last session from one run of config A at 2×. Tonight the same config at the same speedup measured 25.293 s — +1.58% apart. At 1× config A's `e2e_p95` CV is 0.19% over 14 repeats; two single runs at 2× differ by roughly eight times that. Two runs cannot establish a trend, but if run-to-run spread grows with load then a guard anchored on one run at the target speedup is softer than it looks, and the anchors deserve repeats before anyone leans on them.

These are single runs. `NOISE_REPORT.md` and `LADDER_REPORT.md` supply the error bars: throughput and `e2e_p95` are resolvable from one run at config A (CV 0.02% and 0.19%), `ttft_p95` is not (CV 0.69% at A, 6.07% and bimodal at J), and no `ttft_p95` conclusion is drawn here.

