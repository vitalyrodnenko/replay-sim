# LOAD_PLAN — pre-registration

**Written and committed 2026-08-29, before any run of this batch.**
**No simulator, `perf.json`, or verdict change.**

## 0. Question

Every config the series has scored moved the *server* — pool size, batch budgets,
caching. The workload itself has never moved. This batch holds the config fixed at A
and moves the arrival rate instead, which is the axis a capacity question actually
lives on. It is **held out by design**: nothing in v0.7 was fitted or tuned against a
compressed trace, and no run in the series has ever exercised one.

## 1. What is run

- **Traces:** `results/trace_s15.jsonl`, `trace_s2.jsonl`, `trace_s3.jsonl` —
  `results/trace.jsonl` with `arrival_s` divided by 1.5, 2 and 3. Prompts, rids,
  prompt/output lengths and order are byte-identical; arrival rate is the only change.
- **Config:** A (`gpu-mem-util 0.85`, mbt 2048, mns 128, prefix caching on) for all.
- **Predictor:** v0.7 as installed in run 7, unmodified, with run-5 `perf.json`,
  unmodified, `--num-blocks 5450`, `--drop-first 10`, `--per-request`.
- **Real runs:** one per scaled trace, `bench --speedup 1` — the scaling lives in the
  trace file, so simulator and bench read the *same* file and `--speedup` stays out of
  it. `--drop-first 10`, `--per-request`, standard protocol (strict VRAM drain,
  asserted pool 87,200, `/health` gate).
- Predictions for all three are generated and **committed before any real run**.

## 2. Expected directions, stated before the data

Recorded so they cannot be adjusted afterwards. As arrival rate rises:

1. **`throughput_tok_s` rises**, with diminishing returns as the server saturates.
2. **`gpu_s_per_1k_out_tok` falls** — the same work is packed into denser batches, so
   GPU-seconds per output token goes down.
3. **All four latency metrics grow** — `ttft_p50`, `ttft_p95`, `e2e_p50`, `e2e_p95` —
   and the tails grow faster than the medians.
4. **`prefix_cache_hit_rate` is not predicted to move much**: the same requests in the
   same order want the same blocks. If it moves materially, that is a finding.

A direction landing the wrong way is recorded as such, whatever the row counts say.

## 3. Scoring

`replay_sim.verdict`, unmodified, config A on the **unscaled** trace as the baseline
row and each scaled trace as the compared config, giving six rows per speedup.

- **Cost metrics** (`throughput_tok_s`, `prefix_cache_hit_rate`): criterion v2 as
  published — relative delta gap ≤ 15 points. These are the rows the decision rests on.
- **Latency metrics**: reported under both v1 and v2, and read with the standing
  caveat that `ttft_p95` has over-predicted by +16% to +52.9% on every pressure-zone
  config since run 3 and is not trusted for a go/no-go.

`gpu_s_per_1k_out_tok` is not measured by `bench.py` and so appears in neither count,
exactly as `verdict.py`'s own docstring says; its predicted values are tabulated and
its direction checked against §2.

## 4. The decision this must produce

`results/LOAD_REPORT.md` ends with one explicit line — **is the cost model safe to
drive tonight's load sweep, yes or no** — and names the single number that decides it.

Fixed here, before the data: **yes** iff every **cost** row across all three speedups
passes v2 (gap ≤ 15 pt) **and** the three directions in §2.1–§2.2 hold. Otherwise
**no**. Latency rows do not veto: the sweep's objective is cost, and its SLO guard is
already known to be the weak half.

## 5. What this batch will not do

No simulator change, no `perf.json` change, no verdict-criterion change, no
re-scoring of any published row, no outlier rejection, and no tuning of anything
against these results.

## 6. Deliverables

- `results/LOAD_REPORT.md`
- `results/load/sim_A_s{15,2,3}.json` + `simpr_*.jsonl` — frozen predictions
- `results/load/real_A_s{15,2,3}.json` + `realpr_*.jsonl`
