# PREDICTIONS run 10 (v0.9) — frozen before any run-10 simulation

**Simulator:** v0.9 from `replay-sim-v0.9-r1.zip`. Single physics change: **requests
whose final prefill chunk runs in a step sample their first token in that same step.**
**Harness:** `bench.py` records `sent_s`; `simulator.py` gains `--dispatch-gap`.
**`perf.json`:** run-5, byte-identical (sha256 `2d15e811…`).
**Canonical trace:** byte-identical (sha256 `4e70250f…`).
**Held-out for the verdict:** config **M** — config A settings on a fresh
burst-geometry trace.

**Disclosure.** One v0.9 simulation preceded this file: config A on the canonical trace,
as an install check that `Perf.load` could read run-5 `perf.json` (the archive reverted
the provenance tolerance for the fifth time). It returned `ttft_p95` 0.577 s against
v0.8's 0.698 s. It informs no prediction below; no prediction concerns config A on the
canonical trace.

Criterion v2 carries the verdict; both counts reported for series continuity.

## Step 0 — dispatch calibration (done, before predictions)

One instrumentation-only run of the existing burst trace (`results/trace_burst.jsonl`,
12 requests all at `arrival_s = 0.0`), config A, pool asserted 87,200. Its numbers do
not count as a result; it exists only to read `sent_s`.

Measured client dispatch spacing, from `results/run10/dispatch_cal_pr.jsonl`:

| | |
|---|---|
| **median inter-send gap** | **0.100 ms** |
| mean | 0.336 ms |
| min / max | 0.100 / 2.000 ms |
| total span, 12 requests | 3.7 ms |

> **Frozen constant: `--dispatch-gap 0.0001` (0.100 ms).**
> Applied to every burst-family prediction (burst trace, config M). Smooth traces
> (canonical: A–L, coldstart) use gap 0.
>
> Recorded now, before it can be reinterpreted: **0.1 ms is negligible against the
> ~0.85 s cost of one 2,048-token prefill step.** The client dispatches all 12 requests
> inside 3.7 ms, so "simultaneous" arrivals really are simultaneous at this resolution.
> Any improvement in the burst's level structure under v0.9 is therefore attributable to
> the same-step sampling change, not to dispatch modelling. If the dispatch gap turns
> out to matter here, that would be the surprise.

## (i) Config H (in-sample) — error decreases ≥5 pt AND the row passes v2 for the first time

Under v0.8, H's `ttft_p95` is **0.652 s** against a measured **0.542 s** = **+20.3%**.
A 5-point decrease requires ≤ +15.3%; passing v2 requires |error| ≤ 15%, which binds.

**Numeric expectation: sim `ttft_p95` ∈ [0.461 s, 0.623 s].**
**Confirmed** iff the error falls by ≥5 pt **and** the row passes v2.

## (ii) Configs F, G, J, K (in-sample) — every `ttft_p95` absolute error decreases

Magnitudes recorded, no pass required.

| config | v0.8 sim | real | v0.8 error | must become |
|---|---|---|---|---|
| F | 2.080 s | 1.360 s | **+52.9%** | < +52.9% |
| G | 0.934 s | 0.829 s | **+12.7%** | < +12.7% |
| J | 0.934 s | 0.705 s | **+32.5%** | < +32.5% |
| K | 2.582 s | 1.885 s | **+37.0%** | < +37.0% |

**Confirmed** iff all four decrease. Any that rises falsifies it, and the direction of
each is reported either way.

## (iii) Burst trace (in-sample), with the calibrated dispatch gap

Measured burst: **6 levels**, max TTFT **4.080 s**, first level **0.320 s**.
Under v0.8: 4 levels, max 4.042 s, first level 1.696 s.

| quantity | window | v0.8 |
|---|---|---|
| level count | **5–7** (6 ± 1) | 4 ✗ |
| max TTFT | **[3.468, 4.692] s** (4.080 ± 15%) | 4.042 ✓ |
| first level | **[0.240, 0.400] s** (0.320 ± 25%) | 1.696 ✗ |

Levels are clustered at a 50 ms tolerance, as in `BURST_PROBE.md`.
**Confirmed** iff all three hold. Partial results are reported per-quantity.

## (iv) Coldstart (in-sample) — per-request |diff| p95 decreases from 587.7 ms

Direction only, no threshold. Under v0.8 it was **587.7 ms**, bit-identical to v0.7.
**Confirmed** iff it falls below 587.7 ms.

## (v) Cost scorecard A–L — every cost gap ≤ 3 pt

`throughput_tok_s` and `prefix_cache_hit_rate`, v0.8 → v0.9, across configs A–L.

## Held-out config M

Config A's settings on a fresh burst-geometry trace, committed before predicting:

- **three prompt sizes, 500 / 1500 / 3000 words, equal counts**
- **bursts of 8**
- **64 requests** — one third of the canonical 192

64 does not divide by 3, so the sizes are allotted **22 / 21 / 21** (the closest to
equal), assigned round-robin so every burst of 8 mixes all three. Recorded here rather
than chosen after seeing results.

M is scored against **config A on the canonical trace as the baseline on both sides**,
as run 9 did for L, so the delta is the effect of this burst geometry. **Its six rows
under v2 carry the verdict.** One real run, `--per-request`; every other real is reused.

**3× load stays out of scope** — an envelope defect pending the saturation fix, per
`LOAD_REPORT.md` and `SATPROBE_REPORT.md`.
