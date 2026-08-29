# NOISE_REPORT — how much of the series' gap structure is the benchmark itself

**Date:** 2026-08-29  
**Pre-registered** in `results/NOISE_PLAN.md`, committed before any run, amended and corrected before any counted repeat.  
**No simulator change. No `perf.json` change. No published verdict is re-scored.**

**Clean repeats:** config A **14**, config J **14**, run alternating with a full server restart, strict VRAM drain and an asserted KV pool before every one.

## Bottom line

1. **The noise is not uniform — it is concentrated in one metric and grows with pool pressure.** `ttft_p95` has a run-to-run CV of **0.7%** on config A but **6.1%** on config J, a factor of 9. Throughput and prefix-cache hit rate are essentially noiseless (CV ≤ 0.05%), and both e2e percentiles are under 0.2%. `ttft_p95` is the metric the series has been unable to fix since run 3, and it is also the only noisy one.
2. **No published verdict row sits inside the measured noise band.** Every failure the series recorded is larger than this benchmark's own reproducibility — but run 6's J and run 5's H clear it by only 1.34× and 1.54×.
3. **A trustworthy `ttft_p95` needs repeats the series never took.** Every published `ttft_p95` rests on a single run; ±10% needs 4 and ±5% needs 9 on the noisier of the two configs measured.

A caveat that limits all three: noise was measured at exactly two pool points, A (util 0.85) and J (0.82). The trend across those two is that a tighter pool is noisier, so configs deeper in the pressure zone — K at 0.75, C at 0.60 — may well be noisier than either, and the bands below would then be too narrow.

## 1. Dispersion across repeats (plan §4)

### Config A (n = 14)

| metric | mean | stdev | CV | min | max | median | range as % of mean |
|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 0.2463 | 0.0015 | **0.63%** | 0.2440 | 0.2490 | 0.2460 | 2.0% |
| `ttft_p95_s` | 0.6494 | 0.0044 | **0.69%** | 0.6440 | 0.6600 | 0.6485 | 2.5% |
| `e2e_p50_s` | 4.8269 | 0.0063 | **0.13%** | 4.8170 | 4.8380 | 4.8265 | 0.4% |
| `e2e_p95_s` | 7.5430 | 0.0146 | **0.19%** | 7.5240 | 7.5670 | 7.5415 | 0.6% |
| `throughput_tok_s` | 207.7 | 0.0 | **0.02%** | 207.7 | 207.8 | 207.7 | 0.0% |
| `prefix_cache_hit_rate` | 0.8552 | 0.0004 | **0.05%** | 0.8550 | 0.8560 | 0.8550 | 0.1% |

### Config J (n = 14)

| metric | mean | stdev | CV | min | max | median | range as % of mean |
|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 0.2461 | 0.0017 | **0.67%** | 0.2430 | 0.2490 | 0.2460 | 2.4% |
| `ttft_p95_s` | 0.8176 | 0.0496 | **6.07%** | 0.7000 | 0.8420 | 0.8365 | 17.4% |
| `e2e_p50_s` | 4.8537 | 0.0070 | **0.14%** | 4.8420 | 4.8660 | 4.8540 | 0.5% |
| `e2e_p95_s` | 8.0287 | 0.0087 | **0.11%** | 8.0130 | 8.0440 | 8.0305 | 0.4% |
| `throughput_tok_s` | 203.9 | 0.0 | **0.00%** | 203.9 | 203.9 | 203.9 | 0.0% |
| `prefix_cache_hit_rate` | 0.8420 | 0.0000 | **0.00%** | 0.8420 | 0.8420 | 0.8420 | 0.0% |

## 2. Within-run bootstrap 95% CI (plan §5)

10,000 resamples of the 182 kept per-request values per run, seed 12345, percentile recomputed with bench.py's own estimator.

| config | metric | median within-run CI width | as % of the value | across-run spread (CV) |
|---|---|---|---|---|
| A | `ttft_p50_s` | 0.0225 s | 9.2% | 0.63% |
| A | `ttft_p95_s` | 0.5041 s | 78.0% | 0.69% |
| A | `e2e_p50_s` | 0.3890 s | 8.1% | 0.13% |
| A | `e2e_p95_s` | 1.0783 s | 14.3% | 0.19% |
| J | `ttft_p50_s` | 0.0235 s | 9.5% | 0.67% |
| J | `ttft_p95_s` | 0.8596 s | 102.9% | 6.07% |
| J | `e2e_p50_s` | 0.4165 s | 8.6% | 0.14% |
| J | `e2e_p95_s` | 1.9283 s | 24.0% | 0.11% |

**What the comparison says, and it is the opposite of what I expected.** The within-run bootstrap CI on `ttft_p95` is enormous — of order the value itself — while the across-run spread is a fraction of a percent on config A. Those two facts are consistent, and together they say something useful.

`ttft_p95` over 182 requests is the 173rd of 182 sorted values: only nine requests sit above it. Resampling those 182 values moves that order statistic a long way, hence the wide bootstrap interval. But every run replays the *same trace*, so the same handful of requests is slow every time, and the measurement repeats to within 0.7% on A.

So the benchmark is **highly repeatable but weakly estimating**. Re-running does not shrink the bootstrap interval — that width is a property of the trace, not of the harness, and only a longer or differently-drawn trace would reduce it. The practical consequence favours what the series already does: compare configs on a fixed trace, where the trace-sampling uncertainty largely cancels, and do not read the absolute `ttft_p95` as an estimate of the workload's true tail.

## 3. Repeats needed for a trustworthy `ttft_p95` (plan §6)

Smallest *n* with t(0.975, n−1)·s/√n ≤ target · mean.

| config | mean | stdev | CV | n for ±5% | n for ±10% | (±5%, z) | (±10%, z) |
|---|---|---|---|---|---|---|---|
| A | 0.6494 s | 0.0044 | 0.69% | **3** | **2** | 2 | 2 |
| J | 0.8176 s | 0.0496 | 6.07% | **9** | **4** | 6 | 2 |

> Every `ttft_p95` number in runs 1–8a rests on **one** run. To state one to ±10% takes **4** repeats on this workload; to ±5%, **9**.

## 4. Published rows that sit inside the measured noise band (plan §7)

**Flagging only. Published verdicts stand and are not recomputed or amended.** A row is flagged when its published gap is small enough that a single pair of measurements could have produced it by chance.

CV is measured only for A and J. For any other config it is a proxy — **primary** uses max(CV_A, CV_J), **sensitivity** uses min. This is the main limitation: configs far from A and J (C at util 0.60, say) may be noisier than either proxy.

**Primary (max proxy): 11 of 82 scored rows fall inside the band.**

**Sensitivity (min proxy): 8 of 82 scored rows fall inside the band.**


### Rows flagged under the primary proxy

| run | config | metric | published gap | 95% noise band | verdict as published |
|---|---|---|---|---|---|
| 2 | D | `ttft_p50_s` | 0.0 pt | ±1.8 pt | OK |
| 2 | D | `ttft_p95_s` | 7.2 pt | ±11.1 pt | OK |
| 3 | F | `throughput_tok_s` | 0.0 pt | ±0.1 pt | OK |
| 3 | G | `ttft_p50_s` | 0.8 pt | ±1.8 pt | OK |
| 4 | F | `ttft_p50_s` | 1.6 pt | ±1.9 pt | OK |
| 4 | G | `ttft_p50_s` | 0.8 pt | ±1.8 pt | OK |
| 5 | H | `ttft_p50_s` | 0.0 pt | ±1.8 pt | OK |
| 5 | I | `ttft_p95_s` | 48.9 pt | ±49.1 pt | OK |
| 6 | J | `ttft_p50_s` | 0.5 pt | ±1.8 pt | OK |
| 7 | K | `prefix_cache_hit_rate` | 0.1 pt | ±0.1 pt | OK |
| 7 | K | `ttft_p50_s` | 0.4 pt | ±1.9 pt | OK |

### The rows that matter

**No published MISS row sits inside the measured noise band.** Every failure the series recorded is larger than this benchmark's own run-to-run spread. The rows flagged above are all rows that PASSED — their small gaps are not evidence of accuracy, merely of gaps too small for this harness to resolve.

### How close the failures came

Every published MISS, ranked by how far outside the noise band it sits. A ratio near 1 means the verdict rests on a difference this harness can barely resolve.

| run | config | metric | published gap | 95% noise band | gap / band |
|---|---|---|---|---|---|
| 6 | J | `ttft_p95_s` | 17.6 pt | ±13.1 pt | **1.34×** |
| 5 | H | `ttft_p95_s` | 15.6 pt | ±10.1 pt | **1.54×** |
| 7 | K | `ttft_p95_s` | 76.3 pt | ±35.2 pt | **2.17×** |
| 3 | F | `ttft_p95_s` | 71.8 pt | ±25.4 pt | **2.83×** |
| 4 | F | `ttft_p95_s` | 77.0 pt | ±25.4 pt | **3.04×** |
| 2 | C | `ttft_p50_s` | 62.5 pt | ±10.3 pt | **6.08×** |
| 1 | B | `ttft_p95_s` | 15588.0 pt | ±2039.9 pt | **7.64×** |
| 1 | C | `ttft_p95_s` | 3187.0 pt | ±387.8 pt | **8.22×** |
| 2 | B | `ttft_p50_s` | 3528.0 pt | ±405.4 pt | **8.70×** |
| 1 | B | `ttft_p50_s` | 7471.9 pt | ±350.1 pt | **21.34×** |

**2 of 20 published misses sit within 2× of the noise band.** They are outside it — the verdicts stand as published — but they are not comfortable margins, and every one of them is a `ttft_p95` row on a pool-pressure config, which is exactly the family the series has been unable to fix since run 3.

## 5. Drift check (plan §8)

Spearman ρ of `ttft_p95` against run index and against GPU temperature at the start of that run, with permutation p-values (10,000 permutations, seed 12345).

| config | n | ρ vs run index | p | ρ vs start temp | p |
|---|---|---|---|---|---|
| A | 14 | -0.124 | 0.670 | +0.231 | 0.436 |
| J | 14 | +0.056 | 0.855 | +0.475 | 0.118 |

## 6. Excluded repeats

1 attempt did not pass the pre-registered cleanliness gate. It was retried, and no repeat was lost:

```
2026-08-29T02:33:22-05:00 J_10 att=1 FAIL_STARTUP (TIMEOUT after 420s) vram_before=255MiB
```

No outlier rejection of any kind was applied, as pre-committed in plan §3.

---

## Unplanned observation — the KV pool is not reproducible across boots

**Hypothesis-generating, not a result of this plan.** Found while probing pool sizes for the config sweep, before the counted repeats began.

Booting identical settings twice gave two different pools:

```
util 0.85, mbt 2048, mns 64  ->  82,656 tokens
util 0.85, mbt 2048, mns 64  ->  87,680 tokens
```
A 5,024-token (6.1%) difference from nothing but a repeated boot. **Configs A and J differ by 5,776 tokens** (87,200 vs 81,424), so the irreproducibility is the same size as the effect this series studies on the pool axis.

The mechanism is **unresolved**. A first-boot/compile-cache story fits the probes but is contradicted by two published points: D (mns 32) was that shape's first boot and came in high, and I (mbt 8192) was a repeat boot and came in low, agreeing with G to 3 tokens across two utilisations.

**The strict drain appears to fix it.** With a wait for total VRAM under 450 MiB before every boot, all 29 boots of the counted queue were granted exactly the expected pool — 15 × 87,200 for A and 14 × 81,424 for J, with no drift and no retry needed on that account. So the irreproducibility is tied to boot conditions the drain controls, not to something irreducible.

Because the pool was asserted on every boot, **none of the repeats above is affected**. Whether any published single-boot run was is not something this batch can answer, and it is not claimed.


---

## Correction, 2026-08-29 — the "grows with pool pressure" reading is falsified

The bottom line above says the noise "grows with pool pressure", and §1's caveat says
configs deeper in the pressure zone "may well be noisier than either" A or J. Both
statements were extrapolations from two points, and `results/LADDER_REPORT.md` has
since measured two more. They are wrong.

| config | util | `ttft_p95` CV | n |
|---|---|---|---|
| C | 0.60 | **0.25%** | 8 |
| K | 0.75 | **0.32%** | 8 |
| J | 0.82 | **6.07%** | 14 |
| A | 0.85 | **0.69%** | 14 |

C and K, the two configs under the most pool pressure, are the *quietest* of the four
— quieter than A. J is a spike, not the top of a ramp.

And J's spread is **bimodal**: two of its fourteen runs sit at 0.700–0.702 s and the
other twelve at 0.828–0.842 s, with nothing between. Its 6.07% CV is the distance
between two modes being averaged, not scatter around one.

**What this does and does not change.** The measured numbers for A and J are
unchanged, and so is §4's result that no published verdict row falls inside the noise
band — that comparison used A's and J's own measured CVs, which stand. What is
withdrawn is the interpretation: there is no monotone relationship between pool
pressure and benchmark noise on this workload, so the §4 sensitivity proxy of
max(CV_A, CV_J) for unmeasured configs is, on this evidence, conservative rather than
optimistic. The three headline numbers in that section's summary are unaffected.
