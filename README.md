# replay-sim v0

Validates the core hypothesis: can an offline replay simulator predict the
effect of a vLLM configuration change within a 15-point delta accuracy bar.

## What runs where

Any CPU box: workload.py, simulator.py, compare.py (pure Python).
GPU box (2x4090): calibrate.py and bench.py (requires vllm installed).

## Protocol

### 0. Setup (GPU box)

    python -m venv .venv && source .venv/bin/activate
    pip install vllm httpx numpy

### 1. Trace (identical for sim and real runs)

    python -m replay_sim.workload --out trace.jsonl \
        --sessions 24 --turns 8 --rate 1.2

Agentic pattern: shared system prompt + per-session preamble + growing
history. To increase load: --rate here or --speedup in bench.py.

### 2. Calibration (GPU box, once)

    python -m replay_sim.calibrate --model $MODEL --tp 2 --out perf.json

Fits the linear step-time model: t = a + b_p*prefill + b_d*n_decode
+ c_kv*kv/1e6.

### 3. Three configs

A (baseline):       --enable-prefix-caching, gpu-mem-util 0.90
B (caching off):    --no-enable-prefix-caching, rest as A
C (shrunk KV pool): --enable-prefix-caching, gpu-mem-util 0.60

### 4. Predictions BEFORE running B and C for real

Take num-blocks from the server startup log ("# GPU blocks: N") for each
gpu-mem-util value; more honest than guessing.

    python -m replay_sim.simulator --trace trace.jsonl --perf perf.json \
        --num-blocks <N_A> --out sim_A.json
    python -m replay_sim.simulator --trace trace.jsonl --perf perf.json \
        --num-blocks <N_A> --no-prefix-caching --out sim_B.json
    python -m replay_sim.simulator --trace trace.jsonl --perf perf.json \
        --num-blocks <N_C> --out sim_C.json

Commit sim_*.json before step 5. Experimental discipline: the prediction
must be on record before the fact.

### 5. Real runs

For each config: start the server, then

    python -m replay_sim.bench --trace trace.jsonl --model $MODEL \
        --out real_A.json      # then real_B.json, real_C.json

Restart the server between runs (clean cache and clean metrics).

### 6. Comparison

    python -m replay_sim.compare \
        --sim sim_A.json sim_B.json sim_C.json \
        --real real_A.json real_B.json real_C.json \
        --labels A B C

PASS = the predicted relative change of every metric (B vs A, C vs A)
is within 15 points of the real relative change.

## Known v0 simplifications (what to tighten on MISS)

- linear prefill cost, no quadratic attention term (breaks on long
  contexts: add a c_p * sum(chunk*ctx) term)
- no CUDA-graph/warmup effects: the first real requests run slower;
  drop the first 5% of requests when comparing
- single-GPU step model; TP=2 adds a communication term
- preemption simplified to recompute; vLLM swap mode not modeled
- sampling cost folded into the constant a

## v1 axis after PASS

A config axis closer to the product: eviction/cache-size comparison
under multi-tenant load, and routing across two replicas (the two 4090s
as two replicas, session-affinity vs round-robin).

---

# v0.2 changelog (2026-08-27, after validation run 1)

Fixes driven by REPORT.md findings, in the order of their evidence:

1. Prefix-cache blocks are published during prefill, not on completion.
   Overlapping requests now share the system prompt (was the dominant
   defect: 1.77x excess prefill manufactured the config-A tail).
2. Incremental KV allocation + routine preemption-by-recompute. Decode
   blocks are allocated lazily per step; failure evicts cold cache, then
   preempts the latest-arrival sequence (was: zero preemptions ever).
3. Prefix cache coupled to the block pool (refcounted, shared capacity).
   Shrinking the pool now degrades hit rate: the config-C sign error is
   fixed (directional check: 0.862 -> 0.604 vs real 0.856 -> 0.597).
4. prefix_cache_hit_rate is token-level, directly comparable to vLLM
   /metrics. Block-lookup rate moved to block_lookup_hit_rate.
5. --block-size is a CLI parameter (hybrid-model prerequisite).
6. calibrate.py decode grid extended to saturated batches (64/96/128) to
   absorb the TP all-reduce cost where it actually bites.
7. bench.py --drop-first N excludes CUDA-graph warmup requests.

# Validation discipline for run 2

Configs A/B/C from run 1 are now DEVELOPMENT data: v0.2 was designed
looking at their results. They can be used as a regression check but
prove nothing. The validation claim requires held-out configs, predicted
and frozen before any real run:

    D (scheduler axis):  gpu-mem-util 0.85, --max-num-seqs 32
    E (pool axis, unseen point): gpu-mem-util 0.70

Recalibrate first (the grid changed), then predict D and E, commit, then
run for real. The bar is unchanged: every config-change delta within 15
points. Report the A/B/C regression numbers separately and label them
"in-sample".

---

# v0.3 changelog (2026-08-27, after validation run 2)

1. Calibration grid redesigned for identifiability: context now varies at
   fixed batch (B=8 at ctx 512/2048/4096, B=32 at 512/2048, B=64 at
   512/1024) alongside the saturated points, so kv is decorrelated from
   batch and c_kv is recoverable. calibrate.py prints decode-fit R^2 and
   warns loudly if c_kv clamps to zero.
2. simulator.py --drop-first N aligns percentile populations with
   bench.py (run 2 compared sim over 192 requests vs real over 182).

# Run 3 protocol notes

- The 15-point relative bar is UNCHANGED and remains the verdict.
  Additionally report a product scorecard: cost metrics (throughput,
  gpu_s_per_1k, hit rate) and SLA metrics (ttft/e2e percentiles) in two
  separate tables with absolute errors alongside relative gaps. Any
  change to the verdict criterion happens between rounds, in writing,
  never during one.
- A/B/C/D/E are all development data now (D and E informed v0.3's
  calibration redesign). Run 3 held-out candidates: F = pool at an
  unseen point 0.78, G = --max-batched-tokens 8192 (chunked-prefill
  axis, never varied before). Predict, commit, then run.
- Use --drop-first 10 on BOTH bench.py and simulator.py, same N.

---

# VERDICT CRITERION v2

Adopted in writing between runs 4 and 5, prospective from run 5.
Runs 1-4 verdicts stand as published under v1.

VERDICT CRITERION v2 — adopted in writing between runs 4 and 5,
prospective from run 5. Runs 1-4 verdicts stand as published under v1.

Motivation: run 3 §7.4 and run 4 §7 document that a relative-only bar
amplifies sub-second baseline errors into hundred-point gaps and scored
a 40% absolute-error reduction as a regression. Product semantics:
cost questions are asked in relative terms ("how much will we save");
latency questions are asked against absolute SLOs ("will p95 stay
under X ms").

Rules:
1. Cost metrics (throughput_tok_s, gpu_s_per_1k_out_tok,
   prefix_cache_hit_rate): unchanged — relative delta gap <= 15 pt.
2. Latency metrics (ttft/e2e, p50/p95): a row passes if the relative
   delta gap <= 15 pt OR the absolute prediction error on the target
   config's value is <= 15%.
3. Every report shows both counts (v1 and v2) for the full series.
4. Further changes only between rounds, in writing, with motivation.

# v0.6 changelog (2026-08-28, after validation run 5)

Single change: decode-generated full blocks are published to the prefix
cache with unique content, matching vLLM's actual behavior (it caches
every full block of a sequence, not only prompt blocks). On this
workload they earn zero hits but consume cache capacity, so eviction
pressure persists to larger pools. Directional check: sim hit rate now
responds to pool size near saturation (0.808/0.847/0.862 at
4607/5450/5811 blocks; was flat 0.862 at the top two), reproducing the
run-5 config-H mechanism.

# Run 6 protocol

- Criterion v2 (adopted between runs 4 and 5) carries the verdict;
  report both counts for series continuity.
- Held-out: J = gpu-mem-util 0.82, mns 128, mbt 2048. Probe its pool
  from its own startup log. One fresh real run (J); A-I reals reused
  from runs 3 and 5, labeled in-sample re-predictions.
- Pre-registered predictions to freeze before simulating:
  (i)  sim hit rate differs between A and H pools (5,450 vs 5,811),
       with sim A moving toward real A's 0.855-0.856;
  (ii) H ttft_p95 over-prediction shrinks and the H row passes v2;
  (iii) J passes v2 on all six rows;
  (iv) cost scorecard unchanged within noise (every cost gap <= 3 pt);
  (v)  F and G ttft_p95 absolute errors shrink (they sit in the same
       cache-saturation zone) -- record even if they stay misses.

> NOTE on this drop-in (run 6). The v0.6 archive's README does not carry
> VERDICT CRITERION v2, which was adopted in writing between runs 4 and 5 and
> which the Run 6 protocol above depends on ("Criterion v2 ... carries the
> verdict"). The criterion is preserved verbatim above rather than dropped.
> The archive also shipped a pre-run-4 calibrate.py and the pristine pre-fix
> workload.py for the third time; neither was copied. simulator.py was taken
> from the archive as delivered, with only Perf.load's provenance-key tolerance
> re-applied so it can read the v0.5 perf.json at all.

# v0.7 changelog (2026-08-28, after validation run 6)

Single change: release() unpins blocks in reverse chain order, so chain
leaves and generated junk enter the eviction queue before chain roots.
The flat LRU was evicting shared-prefix roots first, which made whole
chains unmatchable and charged a full prompt recompute where vLLM
preserves the surviving prefix (leaf-first prefix-tree eviction). This
is the direct cause of run 6's uniform ttft_p95 over-prediction and
the F sign flip.

# Run 7 protocol

- Criterion v2 carries the verdict; both counts for series continuity.
- Held-out: K = gpu-mem-util 0.75, mns 128, mbt 2048 (pressure zone,
  where partial vs full recompute matters most). One fresh real run.
  A-J reals reused, labeled in-sample re-predictions.
- Pre-registered predictions to freeze before simulating:
  (i)   every positive ttft_p95 error decreases; F moves the most;
        J's ttft_p95 passes v2 in-sample;
  (ii)  e2e_p95 errors and the cost scorecard stay within noise;
        hit rates in the pressure zone rise slightly toward real;
  (iii) H does NOT move materially (stays near +20%): its mechanism
        (real tail relief from surplus pool with no eviction pressure)
        is not represented; this prediction makes H a test of that
        claim rather than an inherited hope;
  (iv)  K passes v2 on all six rows.

> NOTE on this drop-in (run 7). Only simulator.py and the two sections above
> were taken from the v0.7 archive. The archive again shipped a pre-run-4
> calibrate.py (3,516 B vs the installed 23,319 B carrying the online modes)
> and the pristine pre-fix workload.py -- the FOURTH consecutive drop-in to do
> so -- and a README without VERDICT CRITERION v2 or any run 4-6 material.
> None of that was installed; trace sha256 verified unchanged. simulator.py was
> taken as delivered with only Perf.load's provenance-key tolerance re-applied,
> which the archive reverted again and without which it cannot read perf.json.
