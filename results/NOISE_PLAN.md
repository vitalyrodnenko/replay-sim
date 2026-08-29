# NOISE_PLAN — pre-registration

**Written and committed 2026-08-28, before any run of this batch.**
**Simulator and `perf.json` are not touched by this work.**

This document fixes the analysis in advance. Anything not specified here does not
get reported as a finding in `results/NOISE_REPORT.md`. If something unplanned and
interesting turns up, it goes in a clearly separated **"Unplanned observations"**
section, explicitly labelled as hypothesis-generating and not a result.

## 0. Question

Every verdict in runs 1–7 rests on a **single** measurement of each config. This
batch measures how much of the published gap structure could be the benchmark
measuring itself. It does **not** re-score anything.

## 1. Design

- Configs: **A** (`gpu-mem-util 0.85`, `mbt 2048`, `mns 128`, prefix caching on)
  and **J** (`0.82`, `mbt 2048`, `mns 128`, prefix caching on) — exactly as
  `scripts/serve.sh` defines them for the published series.
- **14 repeats each**, run **alternating A, J, A, J, …**, starting with A, so any
  monotone thermal or clock drift loads equally onto both configs and largely
  cancels in the A↔J contrast.
- Full **server restart between every repeat**; `/health` readiness gate;
  `--drop-first 10`; `--per-request` on every run.
- Identical trace (`results/trace.jsonl`, 192 requests, sha recorded in the report)
  and identical `MODEL` for all 28 runs.
- `nvidia-smi` (temperature, SM/memory clocks, power, utilisation, throttle
  reasons) sampled **once per minute for the whole night** into
  `results/thermal/thermal_night.csv`, plus a 5 s per-run sampler into
  `results/thermal/nv_<cfg>_<rep>.csv`.

## 2. Metrics

Exactly the six the series scores, as emitted by `replay_sim.bench`:

`ttft_p50_s`, `ttft_p95_s`, `e2e_p50_s`, `e2e_p95_s`, `throughput_tok_s`,
`prefix_cache_hit_rate`.

Percentiles are recomputed with **bench.py's own estimator**,
`sorted(v)[min(len(v)-1, int(q*len(v)))]`, so every number here is about the same
statistic the published reports use. No other percentile definition is reported.

## 3. Inclusion and exclusion — fixed now, before any data

A repeat is **clean** iff all of: the server reached `/health`; `bench` exited 0;
the summary reports exactly **182** requests after the drop; and the bench log
contains no traceback.

- Failed startup (CUDA-graph OOM is known at these settings): tear down, wait for
  VRAM to drain, **retry once**. On a second failure, **skip that repeat** and
  record it. The queue is never blocked by one bad run.
- **No outlier rejection of any kind.** Every clean repeat enters every statistic.
  This is pre-committed precisely so that a wide tail cannot be tidied away later.
- Excluded repeats are listed individually in the report with their reason.
- Target: **≥12 clean repeats per config**. If a config finishes with <12, the
  report says so and every derived number for it is labelled under-powered.

## 4. Analysis A — dispersion across repeats

Per config × metric: **n, mean, sample stdev (ddof=1), CV = stdev/mean, min, max**,
and for description only, median and the min–max range as a percentage of the mean.

## 5. Analysis B — bootstrap 95% CI *within* single runs

Per run, per percentile metric (`ttft_p50/p95`, `e2e_p50/p95`): resample the 182
kept per-request values with replacement, **B = 10,000**, seed **12345**, recompute
the percentile with the estimator in §2, and take the 2.5th/97.5th percentiles of
the bootstrap distribution. Reported per run and summarised as the median CI width
across runs.

This is deliberately paired with Analysis A to answer one question:
**how much of the run-to-run spread is within-run sampling noise, and how much is
the restart itself** (cache state, allocation, clocks)? The comparison of the two
widths is a pre-registered output. Throughput and hit rate are single-valued per
run and get no within-run CI.

## 6. Analysis C — repeats needed for a ±5% and ±10% CI on `ttft_p95`

Smallest integer *n* ≥ 2 such that the half-width of a 95% CI on the **mean**
`ttft_p95` is within the target fraction of that mean:

> t(0.975, n−1) · s / √n ≤ target · mean,  target ∈ {0.05, 0.10}

using *s* and *mean* from §4, solved by search over n ≤ 1000. Reported per config.
The same figure using z = 1.96 is reported alongside as a reference. If the
required *n* exceeds the repeats actually collected, the answer is reported as an
extrapolation from the measured *s* and labelled as such.

## 7. Analysis D — which published rows sit inside the measured noise band

**Flagging only. Published verdicts stand and are not recomputed, re-scored, or
amended.** This section identifies rows whose published gap is small enough that a
single pair of measurements could have produced it by chance.

Rows are read from the frozen published artifacts: `results/verdict_heldout_run{5,6,7}.json`,
and for runs 1–4 recomputed from the frozen `sim_*.json` / `real_*.json` pairs via
the unmodified `replay_sim.verdict.score`. Recomputation reproduces the published
gaps; it does not change them.

For a row (config X vs baseline A, metric m) with published `real_delta` d:

> sd(d) ≈ |1 + d| · √(CV_A² + CV_X²) ,  half-width = 1.96 · sd(d) · 100 points

A row is **flagged** iff its published `gap` (in points) ≤ that half-width.
For the v2 absolute-error limb, a row is flagged iff |`abs_err`| ≤ 1.96 · CV_X.

**CV_X is measured only for A and J.** For every other config it is a proxy, and
this is the main limitation of this analysis:
- **Primary:** CV_X = CV_J for X=J, CV_A for X=A, else **max(CV_A, CV_J)**.
- **Sensitivity:** the same table under **min(CV_A, CV_J)**. Both counts reported.

The report states plainly that noise was measured at two pool points on one machine
in one night, and that configs far from A and J (e.g. C at util 0.60) may well be
noisier than either proxy.

## 8. Analysis E — drift check

Pre-registered so it cannot be a post-hoc story: Spearman ρ of `ttft_p95` against
(a) run index within the night and (b) GPU temperature sampled at that run's start,
per config, with p-values. Reported whatever the outcome, including null.

## 9. What this batch will not do

No simulator change, no `perf.json` change, no re-scoring of any published verdict,
no new verdict, no outlier removal, and no claim that any published conclusion is
wrong. The output is an error bar the series has never had.

## 10. Deliverables

- `results/NOISE_REPORT.md` — §4–§8 in that order.
- `results/noise/realpr_<cfg>_<rep>.jsonl` — per-request dump, every clean run.
- `results/noise/real_<cfg>_<rep>.json` — per-run summary.
- `results/noise/queue_log.txt` — one line per attempt: outcome, timings, retries.
- `results/thermal/` — night-long and per-run `nvidia-smi` samples.
