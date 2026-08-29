# replay-sim v0.8 validation report — run 9

**Date:** 2026-08-29
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Held-out config:** **L** — config A's settings on a fresh `--bursty` trace
(`results/trace_bursty.jsonl`, 192 requests, ~37 Poisson bursts of 4–6
near-simultaneous arrivals, 150.7 s span). **Its six rows carry the verdict.**
**Single physics change:** streaming cache consumption — prefill re-matches published
blocks before each chunk.

## Verdict: v1 4 of 6 · v2 **6 of 6 — PASS**

**This is the first PASS in the series.**

| metric | sim L | real L | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| `ttft_p50_s` | 0.883 | 0.843 | +285.6% | +242.7% | 42.9 pt | +4.7% | MISS | **OK** |
| `ttft_p95_s` | 1.971 | 1.788 | +182.4% | +178.5% | 3.9 pt | +10.2% | OK | OK |
| `e2e_p50_s` | 5.325 | 5.641 | +17.6% | +16.5% | 1.1 pt | −5.6% | OK | OK |
| `e2e_p95_s` | 11.576 | 11.509 | +70.4% | +52.8% | 17.6 pt | +0.6% | MISS | **OK** |
| `throughput_tok_s` | 212.600 | 212.500 | +2.1% | +2.3% | 0.2 pt | +0.0% | OK | OK |
| `prefix_cache_hit_rate` | 0.860 | 0.860 | +0.5% | +0.6% | 0.1 pt | +0.0% | OK | OK |

Baseline on both sides is config A on the canonical trace, so the delta being scored is
the effect of burstiness — the axis v0.8 changes. Two rows fail v1 on the relative gap
and are rescued by v2's absolute-error limb at **+4.7%** and **+0.6%**: exactly the case
criterion v2 was adopted for, where a large relative gap sits on top of a small absolute
error. Under v1 alone run 9 would read 4 of 6 and FAIL.

**A caveat this report will not hide.** `ttft_p50` and `e2e_p95` pass on absolute error
while missing the relative bar by 42.9 and 17.6 points. The verdict is genuine under the
criterion in force since run 5, and it is a narrower result than "the simulator now
predicts bursty load".

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
| **9** | **L (bursty)** | **4/6** | **6/6** | **PASS** |

## Product scorecard — L vs A

| metric | A real | L real | real Δ | A sim | L sim | sim Δ | gap |
|---|---|---|---|---|---|---|---|
| `throughput_tok_s` | 207.700 | 212.500 | +2.3% | 208.300 | 212.600 | +2.1% | 0.2 pt |
| `prefix_cache_hit_rate` | 0.855 | 0.860 | +0.6% | 0.856 | 0.860 | +0.5% | 0.1 pt |
| `ttft_p50_s` | 0.246 | 0.843 | +242.7% | 0.229 | 0.883 | +285.6% | 42.9 pt |
| `ttft_p95_s` | 0.642 | 1.788 | +178.5% | 0.698 | 1.971 | +182.4% | 3.9 pt |
| `e2e_p50_s` | 4.842 | 5.641 | +16.5% | 4.529 | 5.325 | +17.6% | 1.1 pt |
| `e2e_p95_s` | 7.534 | 11.509 | +52.8% | 6.795 | 11.576 | +70.4% | 17.6 pt |

Cost rows both under 0.2 points. `gpu_s_per_1k_out_tok` is simulated only (bench does
not measure it, per `verdict.py`'s own docstring) and moves **4.601 → 3.686** from A to
L: bursts pack denser batches, so GPU-seconds per output token fall.

## Pre-registered predictions

Frozen with numbers in `results/PREDICTIONS_run9.md` (`3973a6a`) before any run-9
simulation.

### (i) Burst trace — **PARTIAL**

| | v0.7 | v0.8 | real | target |
|---|---|---|---|---|
| max TTFT | 8.252 s | **4.042 s** | 4.080 s | [3.468, 4.692] |
| step levels | 7 | **4** | 6 | 6 |

**Magnitude confirmed, structure falsified.** The maximum fell 2.04× and landed 0.9%
from the measured value, inside the pre-registered window. The 6-level step structure
did **not** survive: v0.8 produces 4 levels (1.696, 2.545, 3.394, 4.021) against the
measured 6 (0.320, 1.175, 2.023, 2.876, 3.729, 4.080). The simulator never reproduces
the fast first request at 0.320 s — its earliest level is 1.696 s. It now gets the
envelope of the burst right and the internal ordering wrong.

### (ii) Config H — **FALSIFIED**

`ttft_p95` error was **+20.3%** under v0.7 and is **+20.3%** under v0.8: sim 0.652 s
against a measured 0.542 s, unchanged to the millisecond. It did not move toward zero
and it does not pass v2. The prediction required both.

### (iii) Coldstart trace — **FALSIFIED**

Per-request |sim − real| p95 was **587.7 ms** under v0.7 and is **587.7 ms** under
v0.8, against a target of < 100 ms. The per-request TTFTs are **bit-identical** between
the two versions. Coldstart arrivals span 0.12–9.82 s while a 1,920-token prefill takes
~0.8 s, so same-prefix prefills rarely overlap and the re-match has nothing to consume.

### (iv) Config J jitter ensemble — **FAILS, as pre-registered**

20 v0.8 sims, arrival jitter ±25 ms, seeds 0–19, order not re-sorted.

```
0.922 0.923 0.925 0.925 0.925 0.926 0.927 0.929 0.932 0.933
0.934 0.941 0.971 0.972 0.976 0.976 0.982 0.983 0.989 1.004
```

- spread **8.9%** of the minimum, against the container dry-run's stated ~9%
- largest internal gap **30 ms**, against the 126 ms gap between the measured modes
- **0 of 20** land in the low mode (0.700–0.702 s, 2 of 14 measured runs)
- **0 of 20** land in the high mode (0.828–0.842 s, 12 of 14)
- **20 of 20** sit above both

A clustered continuum with no discrete gap, sitting entirely above both measured modes.
This is the recorded expectation and not a defect of v0.8; arrival-order jitter alone
does not express the bimodality. `JMODES_REPORT.md` had already located that bimodality
in **3 requests out of 182**, which an ensemble over global jitter would not be expected
to find.

### (v) A–K cost scorecard — **CONFIRMED**

Worst cost gap across all eleven configs: **0.15 pt** against a ≤ 3 pt bar. Nine of
eleven are 0.00. The container evidence claimed v0.8 is bit-identical to v0.7 on the
canonical trace at 1×; that reproduced exactly on this box.

## v0.7 → v0.8 `ttft_p95` movement

| case | v0.7 | v0.8 | real | err v0.7 | err v0.8 | moved |
|---|---|---|---|---|---|---|
| **burst** | 8.252 | **4.042** | 4.080 | +102.3% | **−0.9%** | **−4.210** |
| coldstart | 0.920 | 0.920 | 0.910 | +1.1% | +1.1% | 0.000 |
| H | 0.652 | 0.652 | 0.542 | +20.3% | +20.3% | 0.000 |
| F | 2.080 | 2.080 | 1.360 | +52.9% | +52.9% | 0.000 |
| G | 0.934 | 0.934 | 0.829 | +12.7% | +12.7% | 0.000 |
| J | 0.934 | 0.934 | 0.705 | +32.5% | +32.5% | 0.000 |
| K | 2.582 | 2.582 | 1.885 | +37.0% | +37.0% | 0.000 |

**One row moved.** v0.8 fires only where same-prefix prefills genuinely overlap, which
on this workload means simultaneous arrivals and nothing else. On the burst it closes a
+102.3% error to −0.9%. On the six pressure-zone and coldstart cases that have carried
the series' failures since run 3, it changes nothing at all — F stays at +52.9%, J at
+32.5%, K at +37.0%.

## What run 9 established, and what it did not

**Established.** A held-out config passes v2 6 of 6 for the first time, on an axis the
simulator had never seen. The change is real and large where it applies: a 2× error on
simultaneous-arrival TTFT becomes sub-1%.

**Not established.** The `ttft_p95` defect the series has chased since run 3 is
untouched. Four of five predictions were falsified or partial, including both that
claimed the change would generalise beyond bursts — (ii) H and (iii) coldstart, each
bit-identical. The pass rests on two rows rescued by v2's absolute limb, and the burst
trace's internal step structure got *worse* (7 levels → 4, against a measured 6). v0.8
is a correct fix to a narrow mechanism, not a general improvement, and run 9 should be
read that way.

The 3× load point remains out of scope: it is an envelope defect (saturation cost) per
`LOAD_REPORT.md` and `SATPROBE_REPORT.md`, not an ordering defect.
