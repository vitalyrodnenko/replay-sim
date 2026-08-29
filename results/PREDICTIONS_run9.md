# PREDICTIONS run 9 (v0.8) — frozen before any run-9 simulation

**Simulator:** v0.8 as installed from `replay-sim-v0.8-r2.zip`, single physics change:
**streaming cache consumption — prefill re-matches published blocks before each chunk.**
**`perf.json`:** run-5, byte-identical (sha256 `2d15e811…`).
**Canonical trace:** byte-identical (sha256 `4e70250f…`).
**Held-out for the verdict:** config **L** = config A settings on `results/trace_bursty.jsonl`.

**Disclosure.** One v0.8 simulation was run before this file was written: config A on the
canonical trace, as an install check that `Perf.load` could read run-5 `perf.json` at all
(the archive reverted the provenance tolerance for the fourth time). It returned
bit-identical numbers to v0.7 on all seven metrics. It informed no prediction below
except as noted in (v), where the README already stated that outcome in advance.

Criterion v2 carries the verdicts; both counts reported for series continuity.

## Scoring of the held-out config

Config L is config A's settings on a different trace, so its six rows are scored with
**config A on the canonical trace as the baseline on both sides** — sim A → sim L
against real A → real L. The delta being scored is therefore the effect of burstiness,
which is the axis v0.8 changes.

---

## (i) Burst trace — sim max TTFT falls ~2× and lands within 15% of 4.08 s; the 6-level step structure survives

**Numeric expectation.** v0.7 predicted a maximum TTFT of **8.252 s** against a measured
**4.080 s** — an over-prediction of 2.02×. v0.8 must bring the simulated maximum into
**[3.468 s, 4.692 s]** (4.080 s ± 15%), i.e. a fall of roughly 2×. Separately, the
measured burst showed **6 discrete TTFT levels** ~0.85 s apart (one full 2,048-token
chunked-prefill step); the simulated trace must still show **6 levels** under the same
50 ms clustering tolerance.

**Confirmed** iff simulated max TTFT ∈ [3.468, 4.692] **and** the simulated level count
is 6. Either half missing is a partial result and is reported as such.

## (ii) Config H — `ttft_p95` error moves from +20.3% toward zero and the row passes v2 for the first time

**Numeric expectation.** v0.7 predicted H's `ttft_p95` at **0.652 s** against a measured
**0.542 s**, an error of **+20.3%**. v2 passes a latency row when the absolute error is
≤ 15%, so v0.8 must land in **[0.461 s, 0.623 s]**. The prediction has two parts: the
error moves *toward zero* (i.e. below +20.3%), and it crosses into passing.

**Confirmed** iff |error| < 20.3% **and** the row passes v2. Movement without a pass is
recorded as partial.

## (iii) Coldstart trace — the mirrored per-request pairs align; per-request |diff| p95 < 100 ms

**Numeric expectation.** Under v0.7 the per-request |sim − real| TTFT distribution on the
14-request coldstart burst had **p95 = 587.7 ms** (max 587.7 ms), carried by four requests
at exactly 1× and 2× the modelled cost of the 720-token uncached remainder. v0.8 must
bring **p95 below 100 ms**.

**Confirmed** iff per-request |diff| p95 < 100 ms over the 14 aligned requests.

## (iv) Config J — jittered ensemble against the two measured modes

**Procedure, fixed here.** 20 v0.8 simulations of config J (util 0.82, 5,089 blocks,
mns 128, mbt 2048) on the canonical trace, `--drop-first 10`. Each run perturbs every
`arrival_s` by a uniform draw in **±25 ms**, using `random.Random(seed)` with
**seeds 0–19** inclusive, one seed per run. Arrival order is *not* re-sorted; only the
timestamps move. The simulated `ttft_p95` of each run is recorded.

**The two measured modes**, from the noise batch's 14 clean J repeats:
**low mode 0.700–0.702 s (2 of 14 runs)**, **high mode 0.828–0.842 s (12 of 14)**, with a
**0.126 s gap** and nothing inside it.

> **PRE-REGISTERED EXPECTATION: this FAILS as a mode-reproduction test.** A container
> dry-run (16 jittered sims at 4090-scale step costs, pressure-zone pools) produced a
> clustered continuum with ~9% spread and no discrete gap, so ordering alone is not
> expected to express bimodality. If both modes DO appear, that exceeds the recorded
> expectation and is the finding.

**Reported either way**: the 20-value distribution, its spread, whether any discrete gap
appears, and where it sits relative to both measured modes. Failure here is the expected
outcome and is not a defect of v0.8.

## (v) Configs A–K cost scorecard — unchanged within noise (every cost gap ≤ 3 pt)

**Numeric expectation.** Across configs A–K, every cost row (`throughput_tok_s`,
`prefix_cache_hit_rate`) must keep a v0.7→v0.8 delta gap of **≤ 3 points**.

> **Container evidence** (recorded in the README before this run): on the canonical trace
> v0.8 is bit-identical to v0.7 at 1× and 2× load (re-match never fires without
> overlapping same-prefix prefills) and shifts 3× by +0.8% throughput / −5% `ttft_p95`,
> slightly worsening the known saturation optimism there. 3× remains out of scope.

The install check above already reproduced the 1× half of that claim on this box: config A
on the canonical trace is bit-identical between v0.7 and v0.8 on all seven metrics.

**Confirmed** iff every A–K cost gap ≤ 3 pt.

---

## What is simulated, and frozen, before any real run

- **Held-out:** config L on `trace_bursty.jsonl` (carries the verdict).
- **In-sample re-predictions:** configs A–K on the canonical trace; the burst trace; the
  coldstart trace; and the 20 jittered J runs of (iv).
- Real runs are reused: A–K from runs 3/5/6/7, burst and coldstart from the probe
  session. Only **config L** is run fresh.

**The 3× load point stays out of scope**: it is an envelope defect (saturation cost), not
an ordering defect, per `LOAD_REPORT.md` and `SATPROBE_REPORT.md`.
