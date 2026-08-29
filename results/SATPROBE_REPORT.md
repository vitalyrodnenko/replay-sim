# SATPROBE_REPORT — does decode step cost stay linear at saturation?

**Date:** 2026-08-29  
**Method:** `replay_sim.calibrate._measure_point`, unmodified — the run-5 online procedure, the same common steady-state window, the same `--warm-tokens 64 --tail-tokens 8`, 3 repeats per point, median reported.  
**`perf.json` is read and never written. v0.7 stays installed. Nothing is refitted into the model.**

Config A, 87,200-token pool asserted at boot. **Zero preemptions at every point**, including the two run at 95% pool occupancy.

## Measured vs the installed linear model

The model is `step = a + b_d·B + c_kv·(B·ctx)/1e6` with run-5's coefficients (a = 12.665 ms, b_d = 0.4137 ms/seq, c_kv = 0.12793).

| B | ctx | measured | model | residual | residual % | gen_tokens | peak KV |
|---|---|---|---|---|---|---|---|
| 96 | 256 | **57.253 ms** | 55.526 ms | +1.727 ms | **+3.11%** | 256 | 49,152 (56%) |
| 96 | 512 | **60.715 ms** | 58.670 ms | +2.045 ms | **+3.48%** | 256 | 73,728 (85%) |
| 112 | 256 | **64.831 ms** | 62.669 ms | +2.162 ms | **+3.45%** | 256 | 57,344 (66%) |
| 112 | 512 | **68.729 ms** | 66.337 ms | +2.392 ms | **+3.61%** | 227 | 82,768 (95%) |
| 128 | 256 | **70.016 ms** | 69.813 ms | +0.203 ms | **+0.29%** | 256 | 65,536 (75%) |
| 128 | 512 | **73.656 ms** | 74.005 ms | -0.349 ms | **-0.47%** | 135 | 82,816 (95%) |
| 32 | 512 | **26.514 ms** | 28.000 ms | -1.486 ms | **-5.31%** | 256 | 24,576 (28%) |

> **Window note.** `_measure_point` holds `B×(ctx+gen_tokens)` KV live. At `gen_tokens = 256` the point (128, 512) needs 98,304 tokens, more than config A's pool and more than any bootable utilisation on this box provides (0.88 caps at 92,976). Points that would exceed 85% of the pool use a shorter `gen_tokens`, sized to stay under 95%; the warm/tail skips are unchanged, so the window is shorter but constructed identically. Every window is ≥62 steps against a 20-step minimum.

## Repeatability against run 5

Three points were already in the run-5 grid, so they are a direct check that this probe reproduces the frozen calibration:

| B | ctx | run 5 | tonight | delta |
|---|---|---|---|---|
| 96 | 512 | 60.862 ms | 60.715 ms | -0.147 ms (-0.24%) |
| 128 | 256 | 70.245 ms | 70.016 ms | -0.229 ms (-0.33%) |
| 32 | 512 | 26.371 ms | 26.514 ms | +0.143 ms (+0.54%) |

All within 0.55%, including the B=32 anchor. The measurement is reproducing the run-5 grid, so the residuals below are the model's, not the probe's.

## The extrapolation test

The installed model was fitted on a grid that *already contains* (96, 512) and (128, 256), so asking whether it predicts high batch is partly circular. Refitting on run-5's points with **B ≤ 64 only** (n = 12, R² = 0.99884, a = 13.031 ms, b_d = 0.3690 ms/seq, c_kv = 0.14147) and extrapolating gives the honest picture:

| B | ctx | measured | low-batch model | residual % |
|---|---|---|---|---|
| 96 | 256 | 57.253 ms | 51.936 ms | **+10.24%** |
| 96 | 512 | 60.715 ms | 55.413 ms | **+9.57%** |
| 112 | 256 | 64.831 ms | 58.420 ms | **+10.97%** |
| 112 | 512 | 68.729 ms | 62.476 ms | **+10.01%** |
| 128 | 256 | 70.016 ms | 64.904 ms | **+7.88%** |
| 128 | 512 | 73.656 ms | 69.540 ms | **+5.92%** |
| 32 | 512 | 26.514 ms | 27.158 ms | **-2.37%** |

## Answer

> **Does step cost leave the linear envelope above B≈96? Yes — a model calibrated below B=64 under-predicts high-batch step time by 5.9% to 11.0%. But at B=128 the *installed* model is accurate to 0.47%, because run 5 already anchored the fit at (96, 512) and (128, 256).**

Concretely at B = 128: measured 70.016 ms at ctx 256 and 73.656 ms at ctx 512, against installed-model predictions of 69.813 and 74.005 ms — +0.29% and -0.47%. The low-batch extrapolation misses the same two points by +7.9% and +5.9%.

Two things follow, and they pull in opposite directions.

**The non-linearity is real but already absorbed.** Step cost genuinely rises faster than a low-batch line predicts — by about 10% by B≈96–112 — so anyone calibrating on small batches and extrapolating would badly under-cost saturation. Run 5's decision to put (96, 512) and (128, 256) in the grid is what keeps v0.7 honest up here.

**But the installed model is not flat-accurate across the range.** It under-predicts by ~3.5% at B = 96–112 and is near-exact at B = 128, so the residual is not monotone in batch: the fit is pinned at its two high-batch anchors and sags between them. A ~3.5% under-prediction of step time at B ≈ 96–112 is an optimistic error in exactly the regime a load sweep drives into, and it is the same sign as the saturation miss `LOAD_REPORT.md` recorded at 3×. This probe does not establish that the two are the same effect, and no coefficient is changed here.

