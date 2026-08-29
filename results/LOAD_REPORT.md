# LOAD_REPORT — does the cost model hold when the workload moves?

**Date:** 2026-08-29  
**Pre-registered** in `results/LOAD_PLAN.md`; predictions frozen and committed before any real run.  
**No simulator, `perf.json`, or verdict change. Nothing is re-scored.**

Config A held fixed; the arrival rate moved. Every config the series has scored until now moved the *server*. This axis is held out by design — nothing in v0.7 was fitted against a compressed trace.

## The decision

> ## Is the cost model safe to drive tonight's load sweep? **NO**

**The number that decides it: 15.4 points**, the `throughput_tok_s` delta gap on the 3× trace, against a 15-point bar. It misses by 0.4 points.

The pre-registered rule was: yes iff **every** cost row passes v2 across all three speedups and the throughput/`gpu_s` directions hold. The directions hold. 5 of 6 cost rows pass. One does not, so the answer is no.

### What that hides, and it matters more than the verdict

The failure is not spread across the load axis — it is entirely at 3×:

| speedup | cost rows passing v2 | worst cost gap | all rows v1 | all rows v2 |
|---|---|---|---|---|
| 1.5× | 2/2 | 0.3 pt | 5/6 | 5/6 |
| 2× | 2/2 | 0.7 pt | 5/6 | 6/6 |
| 3× | 1/2 | 15.4 pt | 1/6 | 3/6 |

**The cost model is sound to 2× and breaks at 3×.** At 1.5× and 2× every cost row passes with gaps of 0.7 points or less — throughput predicted to within 0.1% and 0.7% absolute. At 3× the throughput gap jumps to 15.4 points.

**And it breaks in the dangerous direction.** At 3× the model predicts throughput rising +113.6% over baseline where the server actually delivered +98.2%. It thinks the server absorbs more load than it does — it under-models saturation. A capacity sweep leaning on it would place configs beyond where they can actually run, and would do so optimistically.

## Expected directions (plan §2), checked against the real runs

| # | expectation | measured | holds? |
|---|---|---|---|
| 1 | throughput rises, diminishing | 207.7 → 305.2 → 392.6 → 411.7 tok/s | **yes** |
| 2 | `gpu_s_per_1k` falls (predicted; bench does not measure it) | 4.601 → 3.229 → 2.523 → 2.242 | **yes** |
| 3 | latencies grow, tails faster | e2e_p95 7.5 → 11.6 → 24.9 → 48.5 s | **yes** |
| 4 | hit rate ~flat | 0.855 → 0.856 → 0.857 → 0.858 | **yes** |

All four hold. The model gets the *shape* of the load response right everywhere; what it loses at 3× is the magnitude of saturation.

## Sim vs real, per speedup

### 1.5× — `trace_s15.jsonl` (arrival span 104 s)

| metric | predicted | measured | error |
|---|---|---|---|
| `ttft_p50_s` | 0.297 | 0.286 | +3.8% |
| `ttft_p95_s` | 1.187 | 0.933 | +27.2% |
| `e2e_p50_s` | 6.610 | 6.888 | -4.0% |
| `e2e_p95_s` | 11.268 | 11.625 | -3.1% |
| `throughput_tok_s` | 305.400 | 305.200 | +0.1% |
| `prefix_cache_hit_rate` | 0.856 | 0.856 | +0.0% |

### 2× — `trace_s2.jsonl` (arrival span 78 s)

| metric | predicted | measured | error |
|---|---|---|---|
| `ttft_p50_s` | 0.407 | 0.436 | -6.7% |
| `ttft_p95_s` | 1.636 | 1.505 | +8.7% |
| `e2e_p50_s` | 12.599 | 13.808 | -8.8% |
| `e2e_p95_s` | 21.274 | 24.900 | -14.6% |
| `throughput_tok_s` | 395.200 | 392.600 | +0.7% |
| `prefix_cache_hit_rate` | 0.857 | 0.857 | +0.0% |

### 3× — `trace_s3.jsonl` (arrival span 52 s)

| metric | predicted | measured | error |
|---|---|---|---|
| `ttft_p50_s` | 1.160 | 2.531 | -54.2% |
| `ttft_p95_s` | 14.901 | 20.029 | -25.6% |
| `e2e_p50_s` | 30.612 | 35.812 | -14.5% |
| `e2e_p95_s` | 46.089 | 48.516 | -5.0% |
| `throughput_tok_s` | 445.000 | 411.700 | +8.1% |
| `prefix_cache_hit_rate` | 0.859 | 0.858 | +0.1% |

## Full row scoring

Baseline is config A on the unscaled trace, both sides.

| speedup | metric | kind | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| 1.5× | `ttft_p50_s` | latency | +29.7% | +16.3% | 13.4 pt | +3.8% | OK | OK |
| 1.5× | `ttft_p95_s` | latency | +70.1% | +45.3% | 24.7 pt | +27.2% | MISS | MISS |
| 1.5× | `e2e_p50_s` | latency | +45.9% | +42.3% | 3.7 pt | -4.0% | OK | OK |
| 1.5× | `e2e_p95_s` | latency | +65.8% | +54.3% | 11.5 pt | -3.1% | OK | OK |
| 1.5× | `throughput_tok_s` | cost | +46.6% | +46.9% | 0.3 pt | +0.1% | OK | OK |
| 1.5× | `prefix_cache_hit_rate` | cost | +0.0% | +0.1% | 0.1 pt | +0.0% | OK | OK |
| 2× | `ttft_p50_s` | latency | +77.7% | +77.2% | 0.5 pt | -6.7% | OK | OK |
| 2× | `ttft_p95_s` | latency | +134.4% | +134.4% | 0.0 pt | +8.7% | OK | OK |
| 2× | `e2e_p50_s` | latency | +178.2% | +185.2% | 7.0 pt | -8.8% | OK | OK |
| 2× | `e2e_p95_s` | latency | +213.1% | +230.5% | 17.4 pt | -14.6% | MISS | OK |
| 2× | `throughput_tok_s` | cost | +89.7% | +89.0% | 0.7 pt | +0.7% | OK | OK |
| 2× | `prefix_cache_hit_rate` | cost | +0.1% | +0.2% | 0.1 pt | +0.0% | OK | OK |
| 3× | `ttft_p50_s` | latency | +406.6% | +928.9% | 522.3 pt | -54.2% | MISS | MISS |
| 3× | `ttft_p95_s` | latency | +2034.8% | +3019.8% | 985.0 pt | -25.6% | MISS | MISS |
| 3× | `e2e_p50_s` | latency | +575.9% | +639.6% | 63.7 pt | -14.5% | MISS | OK |
| 3× | `e2e_p95_s` | latency | +578.3% | +544.0% | 34.3 pt | -5.0% | MISS | OK |
| 3× | `throughput_tok_s` | cost | +113.6% | +98.2% | 15.4 pt | +8.1% | MISS | MISS |
| 3× | `prefix_cache_hit_rate` | cost | +0.4% | +0.4% | 0.0 pt | +0.1% | OK | OK |

**Totals: v1 11 of 18, v2 14 of 18.** The latency rows at 3× are the known-bad half and were declared non-vetoing in the plan; they are reported, not scored against the decision. `ttft_p95` at 3× misses by 985 points.

