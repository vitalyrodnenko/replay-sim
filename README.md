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
