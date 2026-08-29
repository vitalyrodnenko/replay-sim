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

---

# AMENDMENT — recorded 2026-08-29 ~01:10, before any counted repeat was run

Between writing the plan and starting the queue, probing the KV pool for the config
sweep turned up something that forces three changes here. Recording them in writing,
before the run, with motivation — the same discipline the series uses for the verdict
criterion.

## What was found

Booting the *same* settings twice gave two different KV pools:

    util 0.85, mbt 2048, mns 64  ->  82,656 tokens   (first ever boot of that shape)
    util 0.85, mbt 2048, mns 64  ->  87,680 tokens   (second boot, same settings)

A 5,024-token (6.1%) difference from nothing but a repeated boot. Across eight probes
the pattern is consistent: **the first boot of a given (mbt, mns) shape is granted
roughly 5,000 fewer tokens than later boots of that same shape**, which points at
compile/CUDA-graph cache state at profiling time rather than at the config.

This matters here for one specific reason: **config A and config J differ by 5,776
tokens of pool (87,200 vs 81,424)**. The artifact is the same size as the effect. A
short-pool boot of A is nearly indistinguishable from a healthy boot of J, so if it
went unnoticed it would land in the A–J contrast as "benchmark noise" and this report
would be wrong in exactly the direction it is trying to measure.

`scripts/stop_server.sh` returns as soon as total VRAM is under 1500 MiB. On this box
~1,281 MiB of residue is worth ~5,000 KV tokens, so the default drain is not tight
enough to guarantee a clean boot either.

## Changes, and why

1. **Strict VRAM drain before every boot.** Wait until total VRAM is under 450 MiB
   (the idle floor with the desktop session is 255 MiB) rather than accepting the
   1500 MiB default. A boot that cannot reach it is not benchmarked.
2. **The granted pool is asserted, not just recorded.** A boot whose
   `GPU KV cache size` is not exactly the config's published value (A 87,200,
   J 81,424) is rejected as dirty and retried, and every occurrence is logged with
   its pre-boot VRAM. Such a boot is not measuring the config it claims to.
   Configs A and J both use the long-warmed (mbt 2048, mns 128) shape, so this
   should be rare; if it is not, that is itself the finding and the report says so.
3. **One discarded warm-up run** (config A, tagged `A_00`) before the counted
   repeats. It enters no statistic. Without it the only run of the night with a cold
   page cache and idle-temperature GPUs is repeat 1 of config A, which would appear
   in Analysis E as drift that is really a cold start.

## Not changed

The measured quantity, the six metrics, the percentile estimator, the 14×2
alternating design, the no-outlier-rejection rule, and analyses A–E are all exactly
as pre-registered above. The robustness work done at the same time (wall-clock
timeout on the bench step, a global deadline, a consecutive-failure breaker,
attempt-scoped staging so a rejected attempt can never be promoted, and a
single-instance lock) changes no measurement — it only stops a wedged run from
silently becoming data or eating the night.

**These pool findings are reported in NOISE_REPORT.md as an unplanned observation,
clearly labelled, and they do not re-score anything.**

## Correction to the amendment above, same night, before any counted repeat finished

The amendment states that "the first boot of a given (mbt, mns) shape is granted
roughly 5,000 fewer tokens than later boots of that same shape". That reads as an
established mechanism and it is not one — two points in the published series
contradict it:

- **D** (util 0.85, mbt 2048, **mns 32**) was the first boot that shape ever had, in
  run 2, and it came in *high*: 87,840 tokens, +640 above A.
- **I** (util 0.78, **mbt 8192**, mns 128) was a *repeat* of the mbt=8192 shape,
  which G had already booted in run 3, and it came in *low*: 68,768 tokens. G and I
  put the mbt=8192 offset at −4,944 and −4,947 tokens at two different utilisations,
  agreeing to 3 tokens. An artifact would not reproduce that closely across two
  utilisations; a genuine activation cost for a 4× larger prefill budget would.

So the honest statement is narrower, and it is the one the changes actually rest on:

> Booting identical settings twice produced 82,656 and 87,680 tokens. **The KV pool
> is not reproducible across boots**, and the spread is comparable to the 5,776-token
> gap between configs A and J. The mechanism is unidentified. mbt=8192 additionally
> appears to carry a real ≈4,944-token cost, measured consistently at two utilisations.

Nothing about the three changes depends on the mechanism: a strict drain, asserting
the granted pool against the config's published value, and a discarded warm-up are all
motivated by the reproducibility failure alone. NOISE_REPORT.md will report the
observation and explicitly say the cause is unresolved.

## Follow-up, 2026-08-29 — the drain was not the mechanism

The amendment above justified the strict VRAM drain by arguing that
`stop_server.sh`'s 1500 MiB threshold "is not tight enough to guarantee a clean
boot". `results/BOOT_MATRIX.md` has since tested that directly and it is wrong:
across 10 boots alternating the two thresholds, and 4 more that SIGKILLed the server
and restarted within 1–3 s, pre-boot VRAM read 255 MiB every single time and the pool
was 87,200 every single time. The driver reclaims memory faster than either threshold
can matter.

The mechanism is instead the **first boot of a new `(mbt, mns)` shape**: two novel
shapes were each booted twice with the strict drain held constant, and each gained
4,272–5,408 tokens on the second boot while starting 31–35 s faster. That is
compilation and CUDA-graph capture, cached the second time.

**This does not change any measurement.** The strict drain is harmless, the asserted
pool is what actually protected the batches — every boot of A, J, K and C was a
long-warmed shape and landed exactly on its expected value — and no number in
NOISE_REPORT or LADDER_REPORT depends on the rationale being right. What is withdrawn
is the explanation, not the protocol.
