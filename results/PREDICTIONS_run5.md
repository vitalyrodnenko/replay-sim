# PREDICTIONS — run 5 (v0.5, fully online). Frozen before any simulation is run.

**Date:** 2026-08-28
**Verdict criterion:** v2, as adopted in README between runs 4 and 5. Both v1 and
v2 counts are reported for the full series, per rule 3.

## Scope

Complete the online calibration. `b_d` and `c_kv` now come from the same
steady-state-window method run 4 used for `a`, sweeping batch **and** context;
`b_p` is refit online from the same harness (TTFT of a single unloaded request),
so **every coefficient in `perf.json` is now measured on the path `bench.py`
exercises**. `B=16 / ctx=3072` is held out of every fit.

`simulator.py` is unchanged from run 4 (itself byte-identical to v0.3 except
`Perf.load` ignoring provenance keys). The trace, `--drop-first 10`, and the
config definitions are unchanged.

## Calibration result (already known when these predictions were written)

| | a (ms) | b_p | b_d | c_kv | fit R² |
|---|---|---|---|---|---|
| v0.3 offline | 12.935 | 0.00041897 | 0.00032273 | 0.01607 | 0.95147 |
| v0.4 hybrid | 16.111 | 0.00041897 | 0.00032273 | 0.01607 | — |
| **v0.5 online** | **12.665** | **0.00040749** | **0.00041372** | **0.12793** | **0.99618** |

`c_kv` is **8.0× larger** than the offline fit and `a` falls back to roughly its
offline value: run 4's inflated `a` was standing in for a context term the
offline harness could not see. Prefill fit R² = 0.99988, `b_p` −2.7% vs offline.

## Held-out configs — measurements do not exist yet

| | spec | probed pool | blocks |
|---|---|---|---|
| **H** | gpu-mem-util **0.88**, max-num-seqs 128, mbt 2048 | 92,976 tok | **5,811** |
| **I** | gpu-mem-util 0.78, mbt 8192, max-num-seqs 128 | 68,768 tok | **4,298** |

**H was specified at 0.93 and 0.93 is not runnable on this box.** 0.93 and 0.90
both die in CUDA-graph capture; 0.88 is the highest bootable point. The full
ladder, the OOM trace, and a method error I made and corrected while probing are
in `results/logs/pool_ceiling_run5.txt`. **H is run at 0.88**, which is still an
unseen pool point and still above every utilisation used in runs 1–4 (max 0.85),
so the extrapolation H was chosen to test is preserved. This substitution was
decided and written down *before* any prediction was generated.

Note that I's pool (68,768) is **smaller than F's 73,712 at the same 0.78**: the
8192-token prefill budget costs activation memory that would otherwise be KV.
The crossed axes interact before a single request is served.

## Baseline decision, fixed before running

All deltas are computed against **run 3's `real_A.json`**, the frozen baseline
every prior run used. Config A will also be re-run for real in run 5 as a
**drift control only**; its numbers are reported separately and do not enter any
delta or verdict count.

## Pre-registered predictions

### (i) Check-point error — RESOLVED BY THE CALIBRATION, not a blind prediction

> Check-point error drops from 16.3% toward <5%.

`B=16 / ctx=3072`, held out of every fit, measured at 26.42 ms:

| model | predicted | error |
|---|---|---|
| v0.3 | 18.89 ms | −28.5% |
| v0.4 | 22.06 ms | −16.5% |
| **v0.5** | **25.57 ms** | **−3.2%** |

**Threshold met.** Recording plainly that this was computed inside
`calibrate.py` and was therefore known before this document was written — the
check point is a calibration output, so it cannot be a blind prediction of a
later step. It is reported as the calibration's own held-out test, and (ii) and
(iii) below are the genuine pre-registrations.

### (ii) e2e residuals shrink further, on high-batch configs specifically

`c_kv` rose 8× and `kv_read` scales with batch × context, so the new term adds
the most time where the decode batch is largest. Splitting the seven in-sample
configs by regime, with v0.4 mean |e2e err| over {p50, p95}:

| group | configs | v0.4 mean \|e2e err\| |
|---|---|---|
| high-batch / queue-bound | B, C | **9.75%** |
| low-batch | A, D, F, G | **7.13%** |

**Prediction:** the high-batch group improves by **more points** than the
low-batch group. Formally, Δ(B,C) > Δ(A,D,F,G), both measured as the drop in
mean |e2e err| from v0.4 to v0.5.

**Recorded risk.** At a typical config-A decode point the v0.5 step is ~23%
longer than the v0.4 step (`a` 12.7 + `b_d`·B + `c_kv`·kv/1e6 against 16.1 +
smaller terms). v0.4 under-predicted e2e everywhere by 2–22%, so v0.5 may
**overshoot into positive error** on the low-batch configs. If that happens the
low-batch group can get worse while the high-batch group improves — which
satisfies the prediction as written while being a real regression. Both
outcomes are reported.

### (iii) H and I `ttft_p95` under criterion v2 — stated pass/fail

> If queue build-up is the true remaining mechanism, I (long prefill steps +
> tight pool) should still miss while H should pass.

**Predicted: H `ttft_p95` PASSES under v2. I `ttft_p95` FAILS under v2.**

H is a light-load config of the same shape as A, D and G: large pool, 2048-token
prefill budget, no admission pressure. Its `ttft_p95` should track A's closely,
and under v2 it has two ways to pass (relative gap ≤ 15 pt, or absolute error
≤ 15%).

I crosses the two mechanisms that produced every tail miss in runs 3 and 4: an
8192-token prefill budget, where one step can run ~3.4 s and arrivals stack
non-linearly behind it (G's mechanism), and a tight pool at 0.78, where
admission stalls become bursty (F's mechanism). Run 4 §5 confirmed these misses
are independent of the per-step constant, and nothing in run 5 addresses
queueing. I predict I misses on both v2 limbs: relative gap > 15 pt **and**
absolute error worse than −15%.

Recorded for scoring: run 4's F `ttft_p95` failed v2 at −30.3% absolute error;
G's passed v2 at −9.9% despite a 22.9 pt gap.

### Verdict predictions

- **v1 on H+I (12 rows):** 10 or 11 of 12 — every row except I `ttft_p95`, and
  possibly I `ttft_p50`.
- **v2 on H+I (12 rows):** 11 of 12, the miss being I `ttft_p95`.
- Neither criterion reaches PASS, because a single miss fails the run.
