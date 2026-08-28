# PREDICTIONS — run 4 (v0.4 hybrid). Frozen before any simulation is run.

**Date:** 2026-08-28
**Scope: exactly one change.** The per-step constant `a` is refitted against the
online HTTP path. `b_p`, `b_d`, `c_kv` are carried over unchanged from the v0.3
offline fit. The trace, the seven config definitions, the block-pool figure fed
to each prediction, `--drop-first 10`, and the 15-point verdict bar are all
unchanged from run 3. `simulator.py`'s step model is byte-identical to v0.3; the
only edit to that file is `Perf.load` ignoring the new provenance keys in
`perf.json` (no physics touched).

## This run makes no new real measurements of A–G

The `real_*.json` files from run 3 are valid measurements of this hardware and
are reused as-is. Run 4 is therefore a **re-prediction against already-seen
measurements**. It tests the three pre-registered hypotheses below and nothing
else. It cannot re-establish held-out generalisation: F and G were genuinely
held out in run 3, but in run 4 their measurements were already known to the
person choosing the change. **Any claim beyond (i)–(iii) needs a fresh held-out
config in a later run.**

## What the online calibration measured

Server: config A settings (`gpu-mem-util 0.85`, `max-num-seqs 128`,
`max-num-batched-tokens 2048`, prefix caching on), KV pool 87,200 tokens —
identical to run 3's config A. Driven through the same `httpx` streaming client
`bench.py` uses. B streams of pinned length decode in lockstep, so the
inter-token interval inside a common all-B-resident window *is* the engine step
time. Prompts are unique per stream (server-reported prefix cache hit rate 0.0%
throughout), matching the offline fit's `enable_prefix_caching=False`.

Reproducibility: 3 repeats per point agree to within 0.07 ms; the spread across
the B streams of a point is <= 0.01 ms.

| B | ctx | offline (run 3) | **online** | v0.3 model | online − model | implied `a` |
|---|---|---|---|---|---|---|
| 1 | 512 | 13.40 ms | **13.58** | 13.27 | +0.31 | 13.24 |
| 8 | 512 | 15.61 ms | **16.60** | 15.58 | +1.02 | 13.96 |
| 8 | 2048 | 15.33 ms | **18.28** | 15.78 | +2.50 | 15.44 |
| 32 | 512 | 21.36 ms | **26.39** | 23.53 | +2.86 | 15.80 |
| 32 | 2048 | 21.50 ms | **33.50** | 24.32 | +9.19 | 22.12 |

    a_online = 16.111 ms   (offline 12.935 ms, delta +3.176 ms)

Check point held out of the fit — B=16, ctx=3072, the trace's median prompt
length: online 26.36 ms, v0.3 model 18.89 ms, hybrid model 22.06 ms
(**hybrid still under-predicts by 16.3%**).

## Caveat recorded BEFORE predicting, not corrected

**The online overhead is not a constant per step.** The implied intercept runs
from 13.24 ms at B=1 to 22.12 ms at B=32/ctx=2048 — a spread of 8.88 ms, stdev
3.52 ms, larger than the +3.18 ms correction itself. The overhead grows with
both batch and context, which a single `a` cannot represent. The gate in
`calibrate.py` (stdev > 25% of `a_online`) did **not** fire — 3.52 against a
4.03 threshold — so the run proceeds as scoped, but the diagnostic is recorded
here rather than discovered afterwards.

A second observation, recorded now because it bears on `b_d`/`c_kv` and
therefore on any later run: **the offline grid saw essentially no context
dependence while the online grid sees a strong one.** Going from ctx 512 to
2048 at fixed batch: offline −0.28 ms (B=8) and +0.14 ms (B=32); online +1.68 ms
(B=8) and +7.11 ms (B=32). Run 3 §2 flagged the offline decode fit as
non-monotonic and poorly conditioned (R² 0.951). The online measurement is
monotonic and reproducible to 0.07 ms. Under the scope of this run `b_d` and
`c_kv` stay frozen anyway; the consequence is noted in the predictions below.

## Pre-registered hypotheses

### (i) e2e absolute error collapses

*Primary:* mean `|sim − real| / real` over 7 configs × {`e2e_p50_s`,
`e2e_p95_s`} (n=14) drops from the v0.3 value of **22.58%** to **under 10%**.
*Secondary:* all 14 rows move toward zero (all 14 are currently negative).
*Subset, the run-3 §6 metric:* A/D/E e2e rows (n=6) drop from **26.88%** to
under 10%.

### (ii) The cost scorecard is unchanged within noise

Operationalised: every config's `|throughput error|` stays <= 5% (v0.3: <= 1.8%
on six configs, +7.4% on B); every cost delta-gap vs A stays <= 5 pt (v0.3 worst
3.1 pt); `prefix_cache_hit_rate` moves by <= 1 point absolute.

**Recorded risk, stated before running.** I expect (ii) to be at risk in the
throughput column. `a` enters *every* step, so raising it by 3.18 ms lengthens
`gpu_busy` and `makespan` in proportion to the step count. If the online
per-token overhead is pipelined with GPU work rather than serialising against
it, throughput will now be *under*-predicted where v0.3 was slightly over. The
direction is predictable; the magnitude is not. Recording it now makes the
outcome informative either way.

### (iii) F/G `ttft_p95` gaps — recorded, no directional prediction

v0.3 baselines: F `ttft_p95` gap **71.8 pt**, G **22.4 pt**; both MISS. If the
gaps are essentially unmoved, that is evidence the two tail misses are
independent of the per-step constant and belong to the queue-build-up mechanism
of run 3 §7.2. If they move substantially, they are downstream of the same
cause. Either result is recorded as-is.

## Verdict criterion — unchanged

15-point relative bar on the config-change deltas vs A, exactly as runs 1–3.
v0.3 baselines to beat: F+G 10 of 12 rows; in-sample A–E 15 of 23 rows.
