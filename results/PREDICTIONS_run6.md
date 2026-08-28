# PREDICTIONS — run 6 (v0.6). Frozen before any simulation is run.

**Date:** 2026-08-28
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Single physics change:** decode-generated full blocks are published to the prefix
cache with unique content. They earn no hits on this workload but consume cache
capacity, so eviction pressure persists to larger pools.

## Scope and provenance

`perf.json` is **unchanged from run 5** — calibration is out of scope, byte-identical
(`git diff` empty). `simulator.py` is the v0.6 drop-in as delivered, with one
non-physics edit: `Perf.load`'s tolerance for provenance keys, re-applied because the
archive reverted it and the plain loader raises
`TypeError: unexpected keyword argument 'a_source'` on the v0.5 `perf.json`.

The archive shipped a **pre-run-4 `calibrate.py`** (3,516 B against the current
23,319 B with online mode) and the **pristine pre-fix `workload.py`** for the third
consecutive drop-in. Neither was copied. Trace verified unchanged after the swap:
`sha256 4e70250f…`. The archive README also omits VERDICT CRITERION v2, which the
Run 6 protocol itself depends on; it is preserved verbatim in the installed README.

## Held-out config

| | spec | probed pool | blocks |
|---|---|---|---|
| **J** | gpu-mem-util 0.82, mns 128, mbt 2048 | 81,424 tok | **5,089** |

Unseen, and between F (0.78 → 4,607) and A (0.85 → 5,450). **J's six rows under v2
carry the verdict.** A–I are re-predictions against reals from runs 3 and 5 and are
in-sample; they prove nothing about generalisation.

## Pre-registered predictions

### (i) Sim hit rate responds to pool size near saturation

**Expect `sim_A` < `sim_H`**, breaking v0.5's flat 0.862 at both pools, with `sim_A`
landing in **[0.840, 0.860]** against real A's 0.855.

> **Recorded: this is a verification, not a blind prediction.** The v0.6 changelog
> already states the directional check it ran — 0.808 / 0.847 / 0.862 at 4,607 /
> 5,450 / 5,811 blocks. Those numbers were readable before this document was
> written. Scored as confirmed only if my run reproduces them.

v0.5 for reference: sim A 0.862 (real 0.855, **+0.8%**), sim H 0.862 (real 0.862,
**+0.0%**), sim F 0.838 (real 0.812, **+3.2%**).

### (ii) H `ttft_p95` over-prediction shrinks and the H row passes v2

v0.5: sim 0.652 s vs real 0.542 s, **+20.3%**, failing both v2 limbs (gap 15.6 pt).
H holds 361 more blocks than A; once generated blocks consume capacity that headroom
starts to matter, so `sim_H` should now predict a *faster* tail than `sim_A`, in the
direction real H actually moved (−15.6% vs A).

**Expect H `ttft_p95` absolute error inside ±15%, and the H row passing v2.**

### (iii) J passes v2 on all six rows

At 5,089 blocks J sits in the same near-saturation zone v0.6 targets. Expect real J
between F and A on every metric — `ttft_p95` roughly 0.7–1.0 s against A's 0.642, hit
rate roughly 0.83–0.85 — and the simulator inside v2 on all six rows.

**Expect 6 of 6 under v2, i.e. VERDICT v2 = PASS on the held-out config.** This would
be the first PASS in the series.

### (iv) Cost scorecard unchanged within noise — every cost gap ≤ 3 pt

v0.5 worst cost gap was 2.5 pt (C throughput); hit-rate gaps ran 0.5–2.2 pt.

> **Recorded risk.** This change can only **reduce** simulated hit rates — capacity
> is consumed, never freed. The simulator currently *over*-predicts hit rate on every
> config except C, where sim 0.596 against real 0.597 is nearly exact. So C is the one
> config the change should hurt, and at 2,440 blocks it is the most eviction-pressured
> pool in the set. **C's hit-rate gap is the row most likely to break (iv).** If it
> does, the change is right in general and wrong at the small-pool end.

### (v) F and G `ttft_p95` absolute errors shrink

Both sit in the cache-saturation zone. v0.5: **F −31.3%**, **G −15.9%** — the two
rows that fail v2 in-sample. Expect both to shrink in magnitude, recorded even if
they stay misses. F's is the largest surviving latency error in the series.

## What would falsify the run's premise

If J passes and H still fails, the cache-capacity story explains J but not the
mechanism it was built from. If C's hit rate collapses while F/G/H improve, v0.6 is a
correct change with a missing counterweight at small pools rather than a finished one.
