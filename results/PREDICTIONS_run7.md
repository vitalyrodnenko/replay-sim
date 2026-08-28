# PREDICTIONS — run 7 (v0.7). Frozen before any simulation is run.

**Date:** 2026-08-28
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Single physics change:** `release()` unpins blocks in reverse chain order, so chain
leaves and generated junk enter the eviction queue before chain roots. Flat LRU was
evicting shared-prefix roots first, making whole chains unmatchable and charging a full
prompt recompute where vLLM preserves the surviving prefix.

## Scope and provenance

`perf.json` is **byte-identical to runs 5 and 6** (`git diff` empty). Only
`simulator.py` and the two README sections were taken from the v0.7 archive. The one
non-physics edit is `Perf.load`'s provenance-key tolerance, re-applied because the
archive reverted it again; without it the loader raises
`TypeError: unexpected keyword argument 'a_source'` on `perf.json`. Verified before
patching.

**Fourth consecutive drop-in shipping files that must not be installed**: a pre-run-4
`calibrate.py` (3,516 B against the installed 23,319 B carrying the online modes) and
the pristine pre-fix `workload.py`. Neither copied. Trace verified unchanged:
`sha256 4e70250f…`. The archive README again omitted VERDICT CRITERION v2 and all run
4–6 material; only the two named sections were appended.

The delivered change is one line — `for h in reversed(r.pinned)` — at
`simulator.py:185`. Confirmed to be the only physics difference from v0.6.

## Held-out config

| | spec | probed pool | blocks |
|---|---|---|---|
| **K** | gpu-mem-util 0.75, mns 128, mbt 2048 | 67,936 tok | **4,246** |

Unseen, between E (0.70 → 3,644) and F (0.78 → 4,607) — the pressure zone the protocol
names, where partial vs full recompute should matter most. **K's six rows under v2
carry the verdict.** A–J are in-sample re-predictions against reals from runs 3, 5 and
6 and carry no generalisation claim.

## Baseline: the v0.6 `ttft_p95` column these predictions move

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| +14.2% | −8.1% | +5.9% | +25.7% | +12.0% | **+52.9%** | +12.7% | +20.3% | +15.9% | **+32.5%** |

Nine of ten are positive. B is the only negative and the only config with prefix
caching off, so the change cannot touch it.

## Pre-registered predictions

### (i) Every positive `ttft_p95` error decreases; F moves the most; J passes v2

Expect all nine positive errors above to shrink. **F**, at +52.9% with the most room,
moves the most in absolute points — expect it below **+20%**. **J**, at +32.5%, drops
to **≤ 15%** and passes the v2 absolute limb in-sample.

> **Recorded tension between (i) and (iii).** (i) says *every* positive `ttft_p95`
> error decreases. (iii) says H — a +20.3% positive error — does **not** move. These
> cannot both hold. **I score both as written**: if H does not move, (i) is falsified
> on that one row while (iii) is confirmed; if H moves materially, the reverse. My
> expectation is that H does not move, because the change alters eviction *order* and
> H has no eviction pressure to order (hit rate saturated at 0.862, zero preemptions).
> Recording this now rather than resolving it after the fact.

### (ii) `e2e_p95` and cost stay within noise; pressure-zone hit rates rise toward real

v0.6 baselines: mean `e2e_p95` absolute error **4.29%** (its best result), worst cost
gap **2.8 pt**, and pressure-zone hit-rate errors all slightly negative — C −0.8%,
E −0.4%, F −0.5%, I −1.0%.

Expect mean `e2e_p95` absolute error to stay **≤ 6%**, every cost gap **≤ 3 pt**, and
the hit-rate errors on C, E, F, I to move **up** (less negative) as surviving prefixes
are re-matched rather than recomputed.

### (iii) H does **not** move materially — stays near +20%

Operationalised: H's `ttft_p95` absolute error stays within **±3 points of +20.3%**,
i.e. inside [+17.3%, +23.3%], and the H row continues to fail v2.

**This prediction makes H a test rather than an inherited hope.** Run 6 §7 argued that
H's miss is a *different* mechanism — real tail relief from surplus pool with no
eviction pressure — which no eviction-order change can reach. If H moves anyway, that
diagnosis was wrong and the H story needs rewriting. If H stays put, the diagnosis
survives a direct test and H needs its own hypothesis rather than inheriting each
run's cache change.

### (iv) K passes v2 on all six rows

At 4,246 blocks K sits between E and F. Expect real K between them on every metric —
`ttft_p95` roughly 1.4–3.0 s against A's 0.642, hit rate roughly 0.77–0.79 — and the
simulator inside v2 on all six rows.

**Expect 6 of 6 under v2, i.e. VERDICT v2 = PASS.** This would be the first PASS in the
series. Run 6 predicted the same for J and got 5 of 6, missing on `ttft_p95` — the row
v0.7 exists to fix.

## What would falsify the run's premise

If the positive `ttft_p95` errors shrink but K still misses on `ttft_p95`, the eviction
order is one contributor and not the whole story. If they overshoot into negative
errors, v0.7 has replaced a full-recompute charge that was too large with a
partial-recompute credit that is too generous — the mirror of run 6's failure.
