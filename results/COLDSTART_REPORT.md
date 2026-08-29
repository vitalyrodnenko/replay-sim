# COLDSTART_REPORT — the turn-0 burst, per request

**Date:** 2026-08-29  
**Simulator:** v0.7 as installed in run 7, unmodified. **`perf.json`:** run-5, unmodified.  
**Prediction frozen and committed before the real run** (`ebd93b6`).  
**Measurement only. No fix, no hypothesis ranking, no verdict.**

## What was run

`results/trace_coldstart.jsonl` — 14 sessions × 1 turn, generated with the same generator and seed as the canonical trace (`--sys-len 1200 --turn-user 120 --rate 1.2`). Every prompt is 1,920 tokens and every one shares the same 1,200-token system prefix; nothing else is cached. Arrivals span 0.12–9.82 s.

`--drop-first 0` on both sides, unlike the rest of the series: the first requests of the burst are the subject here, so dropping them would delete the measurement. CUDA-graph warmup is inside these numbers by design.

Config A (util 0.85, 5,450 blocks). Summary: sim makespan 13.7 s vs real 13.7 s; sim prefix-cache hit rate 0.58 vs real 0.58.

## Per-request TTFT, ordered by arrival

| # | rid | arrival | sim TTFT | real TTFT | sim − real | error |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.12 s | 0.809 s | 0.828 s | **-0.019 s** | -2.3% ← |
| 1 | 1 | 1.26 s | 0.915 s | 0.327 s | **+0.588 s** | +179.6% |
| 2 | 2 | 1.30 s | 0.883 s | 0.894 s | **-0.011 s** | -1.2% |
| 3 | 3 | 1.36 s | 0.828 s | 0.840 s | **-0.012 s** | -1.4% |
| 4 | 4 | 2.68 s | 0.333 s | 0.332 s | **+0.001 s** | +0.3% |
| 5 | 5 | 4.33 s | 0.339 s | 0.333 s | **+0.006 s** | +1.9% |
| 6 | 6 | 6.33 s | 0.622 s | 0.329 s | **+0.293 s** | +89.3% |
| 7 | 7 | 6.41 s | 0.558 s | 0.571 s | **-0.013 s** | -2.2% |
| 8 | 8 | 7.59 s | 0.920 s | 0.338 s | **+0.583 s** | +172.5% |
| 9 | 9 | 7.65 s | 0.876 s | 0.910 s | **-0.034 s** | -3.8% |
| 10 | 10 | 7.74 s | 0.787 s | 0.821 s | **-0.034 s** | -4.1% |
| 11 | 11 | 9.45 s | 0.332 s | 0.334 s | **-0.002 s** | -0.5% |
| 12 | 12 | 9.78 s | 0.629 s | 0.337 s | **+0.293 s** | +87.1% |
| 13 | 13 | 9.82 s | 0.607 s | 0.626 s | **-0.019 s** | -3.0% |

## Where the overcharge sits

| | n | mean sim − real | min | max |
|---|---|---|---|---|
| first request of the burst | 1 | **-0.019 s** | -0.019 | -0.019 |
| all later requests | 13 | **+0.126 s** | -0.034 | +0.588 |

Summed over the whole burst the simulator is +1.621 s away from reality on TTFT. The first request alone accounts for **-1%** of that.

## Does it scale with position?

Spearman ρ of (sim − real) against arrival position, permutation p-value (10,000 permutations, seed 12345):

- across all 14 requests: **ρ = -0.169**, p = 0.565
- excluding the first request: **ρ = -0.357**, p = 0.232

## The residual is quantised

`perf.json` charges `b_p` = 0.000407 s per prefill token. The uncached remainder of one of these prompts is 1920 − 1200 = **720 tokens**, which the model prices at **0.293 s**.

| rid | arrival | sim − real | as a multiple of the 0.293 s remainder |
|---|---|---|---|
| 1 | 1.26 s | +0.588 s | **2.00×** |
| 8 | 7.59 s | +0.583 s | **1.99×** |
| 6 | 6.33 s | +0.293 s | **1.00×** |
| 12 | 9.78 s | +0.293 s | **1.00×** |

Every request carrying a material residual is within a few milliseconds of an integer multiple of that 0.293 s figure. The remaining 10 requests are flat to within ±0.035 s.

## Observation

The overcharge is **not on the first request**. Request 0 — the only one that arrives with nothing cached and pays the full 1920-token prefill — is predicted to within 0.019 s (-2.3%), and it is *under*-predicted, not over. The residual instead sits on 4 later requests, all of which the simulator records as having hit the 1200-token shared prefix. It does not scale with position: Spearman ρ against arrival order is -0.169 (p = 0.565) across the burst and -0.357 (p = 0.232) with the first request excluded, and the affected requests (rids 1, 8, 6, 12) are scattered through it rather than clustered at either end. What the residual does track is a quantity: it comes in units of 0.293 s, the modelled cost of the 720-token uncached remainder, at 1× on two requests and 2× on two others, with everything else flat. This report states that pattern and stops there — no cause is proposed and no change is recommended.

