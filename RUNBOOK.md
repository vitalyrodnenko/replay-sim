# RUNBOOK: Qwen3.8-27B on 2x4090

Step-by-step plan for the run. General protocol lives in README.md;
this file covers model and hardware specifics.

## Model

Primary: Qwen/Qwen3.8-27B-FP8, TP=2.
The BF16 checkpoint (~56 GB of weights) does not fit in 48 GB; FP8
(~28 GB) splits across the two cards. FP8-on-Ada check: vLLM uses
Marlin kernels; the startup log should not warn about a fallback.

Fallback if FP8/TP=2 misbehaves or runs out of memory: Qwen3-32B-AWQ
with TP=2, or Qwen3-14B on a single card. For validating the
methodology that is actually cleaner (standard attention); Qwen3.8
then becomes the v1 target.

## Important: Qwen3.8 hybrid attention

Only 16 of 64 layers have a KV cache; the rest are DeltaNet with a
constant-size state. Consequences:

1. "# GPU blocks: N" in the startup log will look large for a model
   this size. That is expected; feed N to the simulator as is.
2. RISK: prefix caching for hybrid architectures may be limited or
   disabled in vLLM. After starting the server with
   --enable-prefix-caching, check the log: if you see
   "prefix caching is not supported ..." or the hit rate in /metrics
   stays at zero under config A, the B axis (cache on/off) does not
   work for this model. Use fallback axis B' below.

## Configs

Common server base:

    export MODEL=Qwen/Qwen3.8-27B-FP8
    BASE="vllm serve $MODEL --port 8000 --tensor-parallel-size 2 \
      --max-model-len 8192 --max-num-seqs 128"

A (baseline):
    $BASE --gpu-memory-utilization 0.90 \
      --max-num-batched-tokens 2048 --enable-prefix-caching

B (caching off):
    $BASE --gpu-memory-utilization 0.90 \
      --max-num-batched-tokens 2048 --no-enable-prefix-caching

B' (fallback axis if prefix caching is unavailable for the hybrid
architecture: change the chunked-prefill budget instead):
    $BASE --gpu-memory-utilization 0.90 \
      --max-num-batched-tokens 8192 --enable-prefix-caching
    # simulator side: --max-batched-tokens 8192

C (shrunk KV pool):
    $BASE --gpu-memory-utilization 0.60 \
      --max-num-batched-tokens 2048 --enable-prefix-caching

## Order of operations

1. venv, pip install vllm httpx numpy; unpack the archive.
2. Trace: python -m replay_sim.workload --out trace.jsonl
3. Calibration (~15-20 min including weight download):
   python -m replay_sim.calibrate --model $MODEL --tp 2 --out perf.json
4. Start config A, record N_A ("# GPU blocks") from the log. Verify
   prefix caching (see risk above). Start C for a minute, record N_C,
   shut it down.
5. Simulations BEFORE the real runs, then freeze the files:
   python -m replay_sim.simulator --trace trace.jsonl --perf perf.json \
       --num-blocks N_A --out sim_A.json
   (same for B or B', and for C with N_C)
   git init && git add sim_*.json perf.json trace.jsonl && git commit
6. Real runs, restarting the server for each config:
   python -m replay_sim.bench --trace trace.jsonl --model $MODEL --out real_X.json
7. python -m replay_sim.compare --sim sim_A.json sim_B.json sim_C.json \
       --real real_A.json real_B.json real_C.json --labels A B C

## Notes

- bench.py hits /v1/completions with a raw prompt and ignore_eos, so
  the model's thinking mode does not affect the experiment (no chat
  template is applied; output lengths are pinned).
- Restart the server between runs: clean cache, clean /metrics.
- OOM on config A: drop gpu-mem-util to 0.85 and use the actual N from
  the log; the simulator does not care.
- Expected first-pass MISS: the hybrid architecture breaks the
  "kv_read scales with context" assumption (48 layers read a
  constant-size state). If compare shows a systematic long-context
  error, send the files over: the step-model fix is splitting c_kv
  into an attention part (grows with ctx) and a constant DeltaNet part
  (grows only with batch). That iteration is exactly what this
  experiment exists to drive.
