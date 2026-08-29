# LADDER_REPORT — how benchmark noise scales with KV-pool pressure

**Date:** 2026-08-29  
**Pre-registered** in `results/LADDER_PLAN.md`, committed before any run.  
**No simulator, `perf.json`, or verdict change. Nothing is re-scored.**

Extends NOISE_PLAN analyses A (dispersion) and C (repeats needed) from two utilisation points to four. Configs J and A are taken unchanged from `results/noise/noise_stats.json`; K and C were run tonight under the same protocol — full restart, strict VRAM drain, asserted KV pool, `--drop-first 10`.

**Repeats:** C (util 0.60) **n=8**, K (util 0.75) **n=8**, J (util 0.82) **n=14**, A (util 0.85) **n=14**.

## 1. The curve

`ttft_p95` run-to-run CV against utilisation:

| config | util | KV pool (tokens) | n | `ttft_p95` mean | CV | |
|---|---|---|---|---|---|---|
| **C** | 0.60 | 39,040 | 8 | 27.7009 s | **0.25%** | `█` |
| **K** | 0.75 | 67,936 | 8 | 1.8731 s | **0.32%** | `█` |
| **J** | 0.82 | 81,424 | 14 | 0.8176 s | **6.07%** | `████████████` |
| **A** | 0.85 | 87,200 | 14 | 0.6494 s | **0.69%** | `█` |

### What the curve shows

**It is not monotone.** The two configs under the most pool pressure, C (util 0.60) and K (0.75), are the *quietest* of the four at 0.25% and 0.32% — quieter than A at 0.69%. J stands alone at 6.07%, roughly 25× the quietest point, with lower-pressure and higher-pressure neighbours on either side of it. This is a spike at one utilisation, not a trend across the axis.

**Reproducibility and speed are different axes.** Over the same four configs the *mean* `ttft_p95` spans 0.649 s to 27.7 s — a factor of 43. C is the slowest config measured by a wide margin and also the most repeatable. A config being consistent says nothing about it being good.

Per the plan, this report states the shape and does not fit a model to four points or propose a mechanism.

## 2. All six metrics, all four configs (CV %)

| metric | C (0.60) | K (0.75) | J (0.82) | A (0.85) |
|---|---|---|---|---|
| `ttft_p50_s` | 0.80% | 1.11% | 0.67% | 0.63% |
| `ttft_p95_s` | 0.25% | 0.32% | 6.07% | 0.69% |
| `e2e_p50_s` | 1.04% | 0.70% | 0.14% | 0.13% |
| `e2e_p95_s` | 0.25% | 0.08% | 0.11% | 0.19% |
| `throughput_tok_s` | 0.04% | 0.03% | 0.00% | 0.02% |
| `prefix_cache_hit_rate` | 0.00% | 0.20% | 0.00% | 0.05% |

## 3. Distribution shape

The CV alone hides what the four configs are actually doing. These are the per-run `ttft_p95` values, sorted — the pre-registered min/max/range of analysis A, shown in full:

- **C** (util 0.60, n=8, CV 0.25%): `27.616`, `27.618`, `27.673`, `27.693`, `27.712`, `27.716`, `27.762`, `27.817`
- **K** (util 0.75, n=8, CV 0.32%): `1.861`, `1.869`, `1.871`, `1.875`, `1.875`, `1.876`, `1.878`, `1.880`
- **J** (util 0.82, n=14, CV 6.07%): `0.700`, `0.702`, `0.828`, `0.830`, `0.832`, `0.833`, `0.834`, `0.839`, `0.840`, `0.840`, `0.842`, `0.842`, `0.842`, `0.842`
- **A** (util 0.85, n=14, CV 0.69%): `0.644`, `0.644`, `0.645`, `0.647`, `0.647`, `0.648`, `0.648`, `0.649`, `0.649`, `0.650`, `0.652`, `0.653`, `0.655`, `0.660`

**J is bimodal, not broadly spread.** 2 of its 14 runs sit at 0.700–0.702 s and the other 12 at 0.828–0.842 s, with nothing in between. Its 6.07% CV is the gap between two modes being averaged, not scatter around one. C, K and A are each a single tight cluster.

No outlier rejection was applied and none is proposed — the low mode is real, reproducible behaviour that occurred twice, not a defective run. It is flagged because a CV computed across two modes does not mean what a CV normally means, and the repeats-needed figures in §5 inherit that.

## 4. Dispersion detail (plan §5, analysis A)

### Config C — util 0.60, pool 39,040 tokens (n = 8)

| metric | mean | stdev | CV | min | max | median | range as % of mean |
|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 1.3621 | 0.0109 | **0.80%** | 1.3460 | 1.3790 | 1.3615 | 2.4% |
| `ttft_p95_s` | 27.7 | 0.1 | **0.25%** | 27.6 | 27.8 | 27.7 | 0.7% |
| `e2e_p50_s` | 14.8 | 0.2 | **1.04%** | 14.7 | 15.1 | 14.7 | 3.2% |
| `e2e_p95_s` | 42.8 | 0.1 | **0.25%** | 42.6 | 42.9 | 42.8 | 0.9% |
| `throughput_tok_s` | 171.3 | 0.1 | **0.04%** | 171.2 | 171.4 | 171.3 | 0.1% |
| `prefix_cache_hit_rate` | 0.5970 | 0.0000 | **0.00%** | 0.5970 | 0.5970 | 0.5970 | 0.0% |

### Config K — util 0.75, pool 67,936 tokens (n = 8)

| metric | mean | stdev | CV | min | max | median | range as % of mean |
|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 0.2555 | 0.0028 | **1.11%** | 0.2500 | 0.2590 | 0.2560 | 3.5% |
| `ttft_p95_s` | 1.8731 | 0.0060 | **0.32%** | 1.8610 | 1.8800 | 1.8750 | 1.0% |
| `e2e_p50_s` | 5.1921 | 0.0364 | **0.70%** | 5.1540 | 5.2300 | 5.1975 | 1.5% |
| `e2e_p95_s` | 10.2 | 0.0 | **0.08%** | 10.2 | 10.2 | 10.2 | 0.2% |
| `throughput_tok_s` | 201.0 | 0.1 | **0.03%** | 200.9 | 201.0 | 201.0 | 0.0% |
| `prefix_cache_hit_rate` | 0.7935 | 0.0016 | **0.20%** | 0.7920 | 0.7950 | 0.7935 | 0.4% |

## 5. Repeats needed for a trustworthy `ttft_p95` (plan §5, analysis C)

Smallest *n* with t(0.975, n−1)·s/√n ≤ target · mean.

| config | util | n collected | mean | stdev | CV | n for ±5% | n for ±10% |
|---|---|---|---|---|---|---|---|
| **C** | 0.60 | 8 | 27.7009 s | 0.0681 | 0.25% | **2** | **2** |
| **K** | 0.75 | 8 | 1.8731 s | 0.0060 | 0.32% | **2** | **2** |
| **J** | 0.82 | 14 | 0.8176 s | 0.0496 | 6.07% | **9** | **4** |
| **A** | 0.85 | 14 | 0.6494 s | 0.0044 | 0.69% | **3** | **2** |

## 6. Excluded repeats

None. Every attempt passed the gate on its first try.

No outlier rejection of any kind was applied, as pre-committed in plan §3.

