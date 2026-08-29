# LADDER_PLAN — pre-registration

**Written and committed 2026-08-29, before any run of this batch.**
**No simulator, `perf.json`, or verdict change anywhere in this work.**

## 0. Question

`NOISE_REPORT.md` measured benchmark reproducibility at two pool points and found
`ttft_p95` CV of 0.69% at config A (util 0.85) and 6.07% at config J (util 0.82) —
a factor of nine across a 3.5% change in utilisation. That is two points, and a
two-point trend is a line by construction. This batch adds two more points, far
down the pressure axis, so the shape of the curve can be seen rather than assumed.

It extends **NOISE_PLAN analyses A (dispersion) and C (repeats needed)** to two
further configs. It introduces no new analysis and re-scores nothing.

## 1. Design

- Configs, exactly as `scripts/serve.sh` defines them for the published series:
  - **K** — `gpu-mem-util 0.75`, mbt 2048, mns 128, prefix caching on
  - **C** — `gpu-mem-util 0.60`, mbt 2048, mns 128, prefix caching on
- **8 repeats each**, run **alternating K, C, K, C, …**, starting with K.
- **One discarded warm-up run** (config K, tag `K_00`) first. It enters no statistic.
- Identical protocol to the noise batch, which is now standard for every boot:
  full server restart, **strict VRAM drain below 450 MiB**, `/health` gate,
  **asserted KV pool** (K = 67,936 tokens, C = 39,040 tokens — a boot granted
  anything else is rejected and retried), `--drop-first 10`, `--per-request`.
- Same trace (`results/trace.jsonl`), same model, same 192 requests.

## 2. Metrics

The same six, from `replay_sim.bench`, with bench.py's own percentile estimator:
`ttft_p50_s`, `ttft_p95_s`, `e2e_p50_s`, `e2e_p95_s`, `throughput_tok_s`,
`prefix_cache_hit_rate`.

## 3. Inclusion and exclusion — fixed now, before any data

A repeat is **clean** iff the server reached `/health`, the granted pool matched the
asserted value, `bench` exited 0, the summary reports exactly **182** requests, all
six metrics are non-null, the per-request dump has 192 rows, and the bench log holds
no traceback. One retry on a dirty attempt, then skip and log.

**No outlier rejection of any kind.** Every clean repeat enters every statistic.
Excluded repeats are listed individually with their reason.

## 4. Time budget — declared in advance

This session has a hard stop. **If the clock reaches 75 minutes into this task, the
pair in flight is finished and the queue stops.** Whatever count each config has
reached is what gets reported. **Any config finishing with n < 6 is labelled
under-powered**, and every number derived from it is marked as such in the report.
Config C sits at a quarter of A's pool and may run slower under preemption; if the
ladder is truncated, it will be C that is short, and that is a foreseen outcome
rather than a surprise to be explained afterwards.

## 5. Analyses

**A — dispersion (NOISE_PLAN §4), per config × metric:** n, mean, sample stdev
(ddof=1), CV, min, max, median, and range as a percentage of the mean.

**C — repeats needed (NOISE_PLAN §6):** smallest integer *n* ≥ 2 with
t(0.975, n−1)·s/√n ≤ target·mean for target ∈ {5%, 10%} on `ttft_p95`, by search
over n ≤ 1000, with the z-based figure alongside.

**The curve:** `ttft_p95` CV against utilisation at the four points now measured —
0.60 (C), 0.75 (K), 0.82 (J), 0.85 (A) — with J and A taken unchanged from
`results/noise/noise_stats.json`. All six metrics are tabulated the same way. The
report states the shape observed and does not fit a model to four points.

## 6. What this batch will not do

No simulator change, no `perf.json` change, no verdict change, no re-scoring of any
published row, no outlier removal, no bootstrap (NOISE_PLAN §5 is not extended
here), and no claim about *why* the curve has whatever shape it has.

## 7. Deliverables

- `results/LADDER_REPORT.md` — the four-point curve and the repeats-needed table.
- `results/ladder/real_<cfg>_<rep>.json`, `realpr_<cfg>_<rep>.jsonl` — every clean run.
- `results/ladder/queue_log.txt` — one line per attempt.
