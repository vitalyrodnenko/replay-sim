# replay-sim v0.9 validation report — run 10

**Date:** 2026-08-29
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Held-out config:** **M** — config A's settings on a fresh burst-geometry trace
(`results/trace_M.jsonl`: 64 requests, 8 bursts of 8, prompt sizes 500/1500/3000 words
in counts 22/21/21). **Its six rows carry the verdict.**
**Single physics change:** requests whose final prefill chunk runs in a step sample
their first token in that same step.
**Harness:** `bench.py` records `sent_s`; `simulator.py` gains `--dispatch-gap`.

## Verdict: v1 2 of 6 · v2 **6 of 6 — PASS**

| metric | sim M | real M | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 2.331 | 2.457 | +1059.7% | +898.8% | 160.9 pt | −5.1% | MISS | **OK** |
| `ttft_p95_s` | 4.350 | 4.564 | +653.9% | +610.9% | 43.0 pt | −4.7% | MISS | **OK** |
| `e2e_p50_s` | 9.495 | 9.449 | +111.2% | +95.1% | 16.0 pt | +0.5% | MISS | **OK** |
| `e2e_p95_s` | 15.616 | 15.373 | +130.9% | +104.0% | 26.9 pt | +1.6% | MISS | **OK** |
| `throughput_tok_s` | 158.600 | 158.700 | −23.9% | −23.6% | 0.3 pt | −0.1% | OK | OK |
| `prefix_cache_hit_rate` | 0.570 | 0.570 | −33.4% | −33.3% | 0.1 pt | +0.0% | OK | OK |

**Every absolute error is within 5.1%.** That is the strongest held-out result the
series has produced, and it is worth being precise about why v1 reads 2 of 6 anyway.

**The v1 count is not measuring what it usually measures here.** M's workload is far
from config A's: its measured `ttft_p50` is **+898.8%** against the canonical baseline.
A 15-point *relative* bar on a 900% change is a 1.7% tolerance on the delta, which no
model would clear; the 160.9-point gap corresponds to predicting +1059.7% where reality
gave +898.8%, i.e. an 18% discrepancy on a tenfold change, while the absolute value is
off by 5.1%. The same structural issue appeared in run 9 (L, v1 4 of 6) and is more
extreme here because M's geometry is further from A's. **The v2 verdict stands as the
criterion in force since run 5; the v1 count should be read as a statement about the
baseline distance, not about accuracy.**

## Series, both criteria

| run | held-out | v1 | v2 | verdict (v2) |
|---|---|---|---|---|
| 1 | A/B/C first contact | 1/11 | 1/11 | FAIL |
| 2 | D, E | 12/23 | 18/23 | FAIL |
| 3 | F, G | 10/12 | 11/12 | FAIL |
| 4 | F, G (in-sample) | 10/12 | 11/12 | FAIL |
| 5 | H, I | 10/12 | 11/12 | FAIL |
| 6 | J | 5/6 | 5/6 | FAIL |
| 7 | K | 5/6 | 5/6 | FAIL |
| 9 | L (bursty) | 4/6 | 6/6 | **PASS** |
| **10** | **M (bursts of 8)** | **2/6** | **6/6** | **PASS** |

## Product scorecard — M vs A

| metric | A real | M real | real Δ | A sim | M sim | sim Δ | gap |
|---|---|---|---|---|---|---|---|
| `throughput_tok_s` | 207.700 | 158.700 | −23.6% | 208.300 | 158.600 | −23.9% | 0.3 pt |
| `prefix_cache_hit_rate` | 0.855 | 0.570 | −33.3% | 0.856 | 0.570 | −33.4% | 0.1 pt |
| `ttft_p50_s` | 0.246 | 2.457 | +898.8% | 0.201 | 2.331 | +1059.7% | 160.9 pt |
| `ttft_p95_s` | 0.642 | 4.564 | +610.9% | 0.577 | 4.350 | +653.9% | 43.0 pt |
| `e2e_p50_s` | 4.842 | 9.449 | +95.1% | 4.496 | 9.495 | +111.2% | 16.0 pt |
| `e2e_p95_s` | 7.534 | 15.373 | +104.0% | 6.763 | 15.616 | +130.9% | 26.9 pt |

M costs 23.6% less throughput and loses a third of its cache hit rate — both predicted
to within 0.3 points. `gpu_s_per_1k_out_tok` (simulated only) moves 4.597 → 3.639.

## Step 0 — dispatch calibration

Median client inter-send gap **0.100 ms** (mean 0.336, span 3.7 ms for 12 requests),
frozen as `--dispatch-gap 0.0001` before predicting and applied to the burst family.

As `PREDICTIONS_run10.md` recorded in advance, 0.1 ms is negligible against the ~0.85 s
cost of a 2,048-token prefill step, so it explains none of the improvement below.
**The burst level structure was fixed by the same-step sampling change, not by dispatch
modelling** — exactly as the prediction file said it would have to be.

## Pre-registered predictions — 4 of 5

Frozen in `results/PREDICTIONS_run10.md` (`6cd41c0`) before any run-10 simulation.

### (i) Config H — **CONFIRMED**

`ttft_p95` error **+20.3% → −8.9%** (sim 0.652 → 0.494 s against a measured 0.542 s).
An 11.4-point decrease against a required ≥5, and |error| 8.9% passes v2. H passes for
the first time.

### (ii) F, G, J, K — **FALSIFIED**

| config | v0.8 | v0.9 | real | err v0.8 | err v0.9 | |
|---|---|---|---|---|---|---|
| F | 2.080 | 1.425 | 1.360 | +52.9% | **+4.8%** | ✓ |
| G | 0.934 | 0.692 | 0.829 | +12.7% | **−16.5%** | ✗ **rose** |
| J | 0.934 | 0.692 | 0.705 | +32.5% | **−1.8%** | ✓ |
| K | 2.582 | 1.731 | 1.885 | +37.0% | **−8.2%** | ✓ |

Three of four improved enormously — F by 48.2 points, J by 30.6, K by 28.8. **G went
the other way**, from +12.7% over to −16.5% under. The prediction required all four, so
it is falsified, and the reason is in the movement table below.

### (iii) Burst trace with the calibrated dispatch gap — **CONFIRMED, all three**

| quantity | window | v0.8 | v0.9 | |
|---|---|---|---|---|
| level count | 5–7 | 4 | **6** | ✓ |
| max TTFT | [3.468, 4.692] s | 4.042 | **4.036** | ✓ |
| first level | [0.240, 0.400] s | 1.696 | **0.298** | ✓ |

The level positions themselves, against measured:

```
v0.9   0.298  1.146  1.994  2.843  3.692  4.036
real   0.320  1.175  2.023  2.876  3.729  4.080
```

Six levels, each within 34 ms. Run 9's falsified half is now confirmed: the first
request's TTFT went from 1.696 s (5.3× the measured 0.320 s) to 0.298 s.

### (iv) Coldstart — **CONFIRMED**

Per-request |sim − real| p95 **587.7 ms → 54.1 ms**, a 10.9× reduction. The residual
that `COLDSTART_REPORT.md` measured in units of the 720-token uncached remainder is
gone; run 9 left it bit-identical.

### (v) Cost scorecard A–L — **CONFIRMED**

Worst cost gap **0.89 pt** against a ≤3 pt bar (config C's hit rate; B and C are the
only two above 0.5).

## `ttft_p95` movement, v0.8 → v0.9

| case | v0.8 | v0.9 | real | err v0.8 | err v0.9 | \|err\| moved |
|---|---|---|---|---|---|---|
| burst | 4.042 | 4.036 | 4.080 | −0.9% | −1.1% | −0.1 |
| coldstart | 0.920 | 0.868 | 0.910 | +1.1% | −4.6% | −3.5 |
| **H** | 0.652 | **0.494** | 0.542 | +20.3% | **−8.9%** | **+11.4** |
| **F** | 2.080 | **1.425** | 1.360 | +52.9% | **+4.8%** | **+48.2** |
| G | 0.934 | 0.692 | 0.829 | +12.7% | **−16.5%** | −3.9 |
| **J** | 0.934 | **0.692** | 0.705 | +32.5% | **−1.8%** | **+30.6** |
| **K** | 2.582 | **1.731** | 1.885 | +37.0% | **−8.2%** | **+28.8** |
| A | 0.698 | 0.577 | 0.642 | +8.7% | **−10.1%** | −1.4 |

**This is a uniform shift, not a targeted fix.** v0.9 removes roughly one decode step
of TTFT from every request, cutting simulated `ttft_p95` about 25% across the board. It
therefore cures the large over-predictions — F, J, K, H, which are the rows that have
carried the series' failures since run 3 — and **overshoots the four cases whose error
was already small**, pushing G, A, coldstart and burst negative. Four improved, four
got worse; the four that got worse were all within 13% to begin with.

## What run 10 established, and what it did not

**Established.** A second consecutive held-out PASS, with every absolute error under
5.1% — the best held-out accuracy in the series. Four of five pre-registered
predictions confirmed, including all three parts of (iii), which run 9 had failed. The
`ttft_p95` defect that survived runs 3–9 untouched is substantially corrected: F from
+52.9% to +4.8%, J from +32.5% to −1.8%, K from +37.0% to −8.2%. The coldstart residual
is gone.

**Not established.** The correction is a constant shift, so it trades over-prediction
for under-prediction: G moved from +12.7% to −16.5%, config A from +8.7% to −10.1%, and
four of eight tracked cases ended further from truth than they started. Nothing here
shows the *shape* of the TTFT model is right — only that a systematic one-step
overcharge has been removed. Whether the remaining ±10% scatter is the next defect or
the noise floor is not answered by this run; `NOISE_REPORT.md` puts config A's own
`ttft_p95` run-to-run CV at 0.69%, so ±10% is not noise.

The 3× load point remains out of scope: an envelope defect (saturation cost) per
`LOAD_REPORT.md` and `SATPROBE_REPORT.md`, not an ordering defect.
