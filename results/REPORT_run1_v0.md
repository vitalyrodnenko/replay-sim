# replay-sim v0 validation report

**Date:** 2026-08-27
**Verdict:** **FAIL** — 1 of 11 config-change rows within the 15-point bar.
**Bottom line:** the simulator predicts *aggregate* behaviour well (config A throughput
+0.9%, e2e_p50 −2.3%) and *tail* and *KV-pool-pressure* behaviour badly. On the C axis it
gets the **sign** wrong, not just the magnitude.

---

## 1. Environment

| | |
|---|---|
| Host | `vitaly-ml-workstation`, Linux 7.0.0-30-generic (Ubuntu 24.04) |
| GPUs | 2 × NVIDIA GeForce RTX 4090, 24,564 MiB each, compute capability **8.9** (Ada) |
| Driver / CUDA | **580.173.02** / CUDA **13.0** |
| Python | 3.12.3 |
| vLLM | **0.28.0** |
| torch / transformers / numpy / httpx | 2.13.0 / 5.16.1 / 2.3.5 / 0.28.1 |
| **Model benchmarked** | **`Qwen/Qwen3-32B-AWQ`** (RUNBOOK fallback), snapshot `0499c3ac83fdef8810b907a23894ba91e95eddd8` |
| Quantization / TP | AWQ 4-bit (`auto_awq`), tensor-parallel-size 2 |
| Weights | 18.00 GiB total, **9.01 GiB per GPU** loaded |
| Model attempted first | `Qwen/Qwen3.8-27B-FP8`, snapshot `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` — **could not run the config matrix**, see §6 |

Full capture: `results/logs/environment.txt`. GPU telemetry per run:
`results/logs/nvidia_smi_{A,B,C}.csv`, summarised in `results/logs/nvidia_smi_summary.txt`.
All three benchmark runs saturated both cards (util avg **93.8% / 98.4% / 94.9%** for
A / B / C), so the measurements are GPU-bound, not client-bound.

---

## 2. What was run

Protocol followed in RUNBOOK order. Model switched to the RUNBOOK fallback after the
primary model proved infeasible on this hardware (§6); the switch was approved before
any prediction was made.

1. **Trace** — `workload.py`, 192 requests, 607,756 prompt tokens, 34,919 output tokens,
   156 s arrival span, 24 sessions × 8 turns, Poisson rate 1.2/s.
2. **Calibration** — `calibrate.py` on this box, TP=2, gpu-mem-util 0.85.
3. **Config A brought up, `N_A` recorded from the server log; prefix caching verified
   empirically; config C brought up, `N_C` recorded.**
4. **Predictions generated and git-committed before any real run** (commit `4a454c1`).
5. **Real runs A, B, C**, server fully restarted between each, readiness polled on
   `/health`, never killed early.
6. **compare.py** — full output in `results/compare_output.txt`.

### Step-time model fitted on this hardware (`results/perf.json`, frozen at `16c838c`)

```
prefill  256 tok: 110.3 ms      decode B=1  ctx=512:  13.40 ms/step
prefill  512 tok: 210.4 ms      decode B=8  ctx=512:  15.66 ms/step
prefill 1024 tok: 421.5 ms      decode B=32 ctx=512:  21.42 ms/step
prefill 2048 tok: 840.1 ms      decode B=8  ctx=4096: 18.61 ms/step
prefill 4096 tok: 1716.9 ms     decode B=32 ctx=2048: 22.41 ms/step

a = 0.014146   b_p = 0.00041879   b_d = 0.000186   c_kv = 0.047886
```

`b_p` = 0.419 ms per prefill token is physically plausible for this model, not an
artifact: 2 × 32e9 FLOP/token ÷ (2 × 4090 at realistic MFU) lands in the same place.

### Exact serve commands

```
A  vllm serve Qwen/Qwen3-32B-AWQ --port 8000 --tensor-parallel-size 2 \
     --max-model-len 8192 --max-num-seqs 128 \
     --gpu-memory-utilization 0.85 --max-num-batched-tokens 2048 --enable-prefix-caching
B  ... --gpu-memory-utilization 0.85 --max-num-batched-tokens 2048 --no-enable-prefix-caching
C  ... --gpu-memory-utilization 0.60 --max-num-batched-tokens 2048 --enable-prefix-caching
```
Recorded verbatim in `results/logs/serve_cmd_{A,B,C}.txt`; startup logs in
`results/logs/server_{A,B,C}.log`.

### Consistency check: predicted-with N vs server-measured N

vLLM 0.28 reports KV capacity in **tokens**, not `# GPU blocks`. The simulator's
`Cfg.block_size` is 16, so `num_blocks × 16` reproduces the engine's exact token
capacity. **All three match exactly:**

| Config | gpu-mem-util | Server-measured KV | ÷16 | N used to predict | Match |
|---|---|---|---|---|---|
| A | 0.85 | 87,200 tokens | 5,450 | **5,450** | ✅ exact |
| B | 0.85 | 87,200 tokens | 5,450 | **5,450** | ✅ exact |
| C | 0.60 | 39,040 tokens | 2,440 | **2,440** | ✅ exact |

Config B was verified to allocate the *same* pool as A, so B vs A isolates prefix
caching alone. Derivation recorded in `results/logs/num_blocks_derivation.txt`.

### Axis B validated before predicting

The RUNBOOK flags that prefix caching may be unavailable, requiring fallback axis B'.
It **is** available here and B' was **not** needed. Verified two ways on config A:
no "prefix caching is not supported" warning in the server log, and three same-session
requests drove `/metrics` to a **61.86%** hit rate, with turn 1 hitting exactly 1,920
tokens — precisely turn 0's full prompt length
(`results/logs/prefix_caching_verification_A.txt`).

---

## 3. Results

### Absolute (sim vs real)

| Metric | sim_A | real_A | err | sim_B | real_B | err | sim_C | real_C | err |
|---|---|---|---|---|---|---|---|---|---|
| ttft_p50_s | 0.316 | 0.252 | +25.4% | 37.807 | 48.979 | −22.8% | 0.254 | 1.061 | −76.1% |
| ttft_p95_s | 8.345 | 0.863 | **+867.0%** | 121.099 | 147.048 | −17.6% | 4.335 | 27.952 | **−84.5%** |
| e2e_p50_s | 4.732 | 4.843 | **−2.3%** | 76.105 | 90.86 | −16.2% | 4.522 | 14.295 | −68.4% |
| e2e_p95_s | 38.06 | 7.793 | **+388.4%** | 145.572 | 172.906 | −15.8% | 17.957 | 42.771 | −58.0% |
| throughput_tok_s | 219.6 | 217.7 | **+0.9%** | 120.9 | 110.0 | +9.9% | 219.6 | 179.2 | +22.5% |
| prefix_cache_hit_rate | 0.986 | 0.856 | +15.2% | 0.0 | n/a | — | 0.989 | 0.597 | +65.7% |
| makespan_s | 159.0 | 160.4 | −0.9% | 288.8 | 317.4 | −9.0% | 159.0 | 194.9 | −18.4% |
| preemptions | 0 | **0** | — | 0 | **9** | — | 0 | **10** | — |

### Config-change effect — the actual bar (≤15 points)

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| **B vs A** ttft_p50_s | +11864.2% | +19336.1% | 7471.9 pt | **MISS** |
| **B vs A** ttft_p95_s | +1351.2% | +16939.2% | 15588.0 pt | **MISS** |
| **B vs A** e2e_p50_s | +1508.3% | +1776.1% | 267.8 pt | **MISS** |
| **B vs A** e2e_p95_s | +282.5% | +2118.7% | 1836.3 pt | **MISS** |
| **B vs A** throughput_tok_s | −44.9% | −49.5% | **4.5 pt** | ✅ **OK** |
| **C vs A** ttft_p50_s | −19.6% | +321.0% | 340.7 pt | **MISS** |
| **C vs A** ttft_p95_s | −48.1% | +3138.9% | 3187.0 pt | **MISS** |
| **C vs A** e2e_p50_s | −4.4% | +195.2% | 199.6 pt | **MISS** |
| **C vs A** e2e_p95_s | −52.8% | +448.8% | 501.7 pt | **MISS** |
| **C vs A** throughput_tok_s | +0.0% | −17.7% | 17.7 pt | **MISS** |
| **C vs A** prefix_cache_hit_rate | +0.3% | −30.3% | 30.6 pt | **MISS** |

**PASS/FAIL per metric — 1 PASS, 10 MISS.** The single metric that clears the bar is
throughput on the prefix-caching axis. Every latency row fails, and every config-C row
fails.

The `prefix_cache_hit_rate` row for B vs A is skipped by `compare.py`: with caching off
the engine reports `prefix_cache_queries_total = 0`, so `bench.py` writes `null`.

---

## 4. Hypotheses for each MISS

Hypotheses only — **no simulator code or `perf.json` was changed**, before or after the
real runs.

### 4.1 Root cause behind every B-vs-A MISS: the A baseline tail, not B

In *absolute* terms `sim_B` is a **uniform 16–23% under-prediction** of `real_B` across
all four latency metrics — respectable. The delta gaps explode because the ratio is taken
against config A, where the simulator over-predicts the tail by **8.7×**
(ttft_p95 8.345 s vs 0.863 s). A relative change measured from a wrong baseline inherits
and amplifies that baseline error. **These four rows are one failure, not four.**

The A tail is over-predicted because the simulator performs **1.77× more prefill work
than the engine did** (154,978 vs 87,596 tokens actually prefilled): it reuses 74.5% of prompt tokens where vLLM reused **85.6%**
(520,160 of 607,756). Mechanism: in `simulate()`, `cache.insert(...)` is called **only in
the `finished` loop**, so a request's blocks become reusable only once it *completes*.
Real vLLM publishes blocks as they are filled during prefill, so requests overlapping in
time immediately share the 1,200-token system prompt. At 1.2 arrivals/s with
e2e_p50 ≈ 4.8 s, roughly six requests are in flight at once and in the simulator **none of
them can share a prefix with each other** — they all miss, all prefill in full, and queue
behind 0.87 s prefill steps that the engine never pays.

*This is not on the README's list.* It is a newly identified v0 simplification and, on
this evidence, the most damaging one for the prefix-caching axis.

### 4.2 The uniform 16–23% under-prediction of config B

Config B is the cleanest compute-bound case in the set: zero reuse, all 607,756 prompt
tokens prefilled, both GPUs at **98.4%** util. The simulator is uniformly *optimistic*.
Best-fit README simplification: **"single-GPU step model; TP=2 adds a communication
term."** The missing per-layer all-reduce is a roughly constant fraction of every step, so
it surfaces exactly as a uniform under-prediction once the engine is saturated. The
measured `SymmMemCommunicator: Device capability 8.9 not supported` warning confirms these
two cards fall back to the standard collective path rather than a fast symmetric-memory
one, so the communication term here is, if anything, larger than on the hardware the model
was conceived for.

Secondary contributor: **"no CUDA-graph/warmup effects — drop the first 5% of requests
when comparing."** That advice was **not** applied; `compare.py` and `bench.py` have no
such filter, so the real numbers still carry first-request warmup, which biases real
latency *upward* and widens this same gap.

### 4.3 Every C-vs-A MISS: the KV pool and the prefix cache are not coupled

The most important finding in this run. **The simulator gets the direction wrong.**

| | config A | config C | direction |
|---|---|---|---|
| sim `prompt_tokens_reused_frac` | 0.745 | **0.802** | reuse *rises* |
| real token hit rate (`/metrics`) | 0.856 | **0.597** | reuse *collapses* |

Cutting the KV pool 57.5% (87,200 → 39,040 tokens) forces real vLLM to evict cached blocks
under load, so 25.9 points more of every prompt must be recomputed — which is why real C is
**+195%** slower at e2e_p50 and loses 17.7% throughput. The simulator predicts C is
*slightly faster* than A.

Mechanism: in the simulator the prefix cache is effectively unbounded relative to the block
pool. `PrefixCache.map` holds hashes with no capacity tied to `num_blocks`; `cache.evict()`
runs **only** when an admission would otherwise fail. Shrinking `num_blocks` therefore
barely perturbs the cache, and the smaller pool merely admits fewer requests concurrently —
which in this step model makes each step *cheaper* and the predicted latency *lower*.
Reality pays for the same pressure through recompute.

*Also not on the README's list.* For a product axis about eviction and cache sizing —
exactly what the README names as the v1 target — this is the blocking defect.

### 4.4 Preemption: 0 predicted, 9–10 observed

README: **"preemption simplified to recompute; vLLM swap mode not modeled."** Confirmed,
and worse than stated — the simulator predicted **zero** preemptions in all three configs
while the engine recorded **9 (B)** and **10 (C)**. `preempt_one()` is reachable only from
the emergency branch `if waiting and not running:`, so it essentially never fires. vLLM
preempts whenever the running set cannot be extended, which is a routine occurrence under a
tight pool. This under-counts the recompute work in exactly the configs (B and C) where it
matters.

### 4.5 The `prefix_cache_hit_rate` row compares two different quantities

Independent of physics, `compare.py` puts non-comparable numbers side by side:

- simulator `prefix_cache_hit_rate` = **block-hash lookups that hit, counted until the
  first miss** (`PrefixCache.match` breaks on first miss) → 0.986 / 0.989.
- vLLM `/metrics` = `prefix_cache_hits_total / prefix_cache_queries_total`, counted in
  **tokens** → 0.856 / 0.597.

The comparable simulator field is `prompt_tokens_reused_frac` (0.745 / 0.802), which is
*not* the field `compare.py` reads. The +15.2% and +65.7% absolute errors on this metric
are therefore partly a measurement-definition artifact. Substituting the correct field does
**not** rescue the row — the direction is still wrong (§4.3) — but the reported magnitude
is not trustworthy as printed.

### 4.6 Not a significant contributor here

**"Linear prefill cost, no quadratic attention term."** The README predicts this bites on
long contexts. This trace tops out at 5,167 tokens and the calibration sweep is very nearly
linear over 256→4096 (110.3 / 210.4 / 421.5 / 840.1 / 1716.9 ms; least-squares
**R² = 0.99984**). There *is* a faint superlinear signature — the per-token slope rises from
0.391 ms/tok on the 256→512 interval to 0.428 ms/tok on 2048→4096, about +9% — which is the
term the README describes. But a 9% drift cannot account for gaps of 200–15,000 points, and
it is swamped by §4.1 and §4.3. It remains a real limitation at longer contexts; it is
simply not what failed today.

---

## 5. Methodology findings (independent of the physics)

### 5.1 The trace vocabulary must be derived from the target model's tokenizer

`workload.py` shipped with `VOCAB = [f"tok{i}" for i in range(512)]` and the comment
"one word per token, approximately". That assumption is false and **silently
model-dependent**:

| Vocabulary | Tokenizer | tokens/word | Largest request | Fits `--max-model-len 8192`? |
|---|---|---|---|---|
| shipped `tok0..tok511` | Qwen3.8 (248,320) | **3.78** | 19,048 tok | 25/192 — **87% would 400** |
| derived for Qwen3.8 | Qwen3-32B (151,669) | **1.346** | 6,913 tok | 192/192 |
| **derived for Qwen3-32B** | Qwen3-32B | **1.0000** | **5,167 tok** | 192/192 |

The shipped vocabulary would have aborted the entire benchmark on the first request
(`bench.py` calls `raise_for_status()`). Worse, when it *doesn't* overflow it corrupts the
experiment quietly: the simulator counts prefill tokens, KV blocks and 16-token prefix
blocks in **words** while `perf.json`'s `b_p` is fitted in **tokens**, so a 1.346× ratio
would have understated real prefill and KV demand by 35% — biasing precisely the C axis.

Final trace verified to **exactly 1.0000 tokens/word, per-prompt, on all 192 requests**
(drift distribution `{0: 192}`), not merely on average — required because prefix caching
operates on exact 16-token block boundaries.
Verification: `results/logs/trace_tokenization_verification.txt`.

**v1 requirement:** `workload.py` must derive its vocabulary from the tokenizer of the
model being benchmarked, and assert 1:1 per prompt, rather than hard-coding a vocabulary
and hoping.

### 5.2 vLLM's KV pool sizing is non-deterministic near the memory ceiling

At `--gpu-memory-utilization 0.90`, three startups of config A gave **one success
(91,808 KV tokens)** and **two OOM failures during CUDA graph capture**, with the memory
profiler sizing the pool at **96,832 tokens** on one of the failures. At 0.85, two
consecutive startups were byte-identical: ready in 35 s, **87,200 tokens** both times.

For an experiment whose independent variable *is* the KV pool size, this matters: `N` must
be read from the log of the run that actually executed, never assumed from a previous
startup at the same setting. Both `sim_*.json` inputs and the real runs were reconciled
against per-run logs (§2 table) for exactly this reason.

### 5.3 Crashed vLLM engines leak workers that silently poison the next run

A failed startup left `VLLM::Worker_TP1` reparented to init holding **24,004 MiB** on
GPU 1. The next launch then failed with a misleading `CUDA error: out of memory` that had
nothing to do with its own configuration. `scripts/stop_server.sh` was hardened to reap
orphaned `VLLM::Worker` / `VLLM::EngineCore` processes and wait for VRAM to drain before
any run begins.

---

## 6. Hybrid architecture findings — `Qwen/Qwen3.8-27B-FP8`

The primary model was attempted first and **could not execute the RUNBOOK's config matrix
on 2×4090**. These are v1 requirements for the simulator, not incidental notes.

Architecture (from `config.json`): 64 layers, `full_attention_interval: 4` →
**16 `full_attention` + 48 `linear_attention` (Gated DeltaNet)**; `head_dim` 256,
24 Q heads / 4 KV heads; DeltaNet 48 V heads / 16 QK heads at head_dim 128,
`mamba_ssm_dtype: float32`.

Measured at `--gpu-memory-utilization 0.90`, TP=2 (`results/logs/calibrate_attempt3_qwen38_mamba_cap.log`):

| Item | Per GPU |
|---|---|
| Weights | 14.54 GiB |
| CUDA graphs (reserved) | 2.30 GiB |
| Activations / overhead | ~2.02 GiB |
| **Available KV cache** | **2.73 GiB** |
| GPU KV cache size | **66,706 tokens**, max concurrency **8.14×** |
| **Mamba cache blocks** | **114** |
| **Attention block size** | **784 tokens** (forced up to match mamba page size) |

### 6.1 Config C is arithmetically impossible

`gpu-memory-utilization 0.60` gives a budget of 0.60 × 23.99 = **14.39 GiB**, but the
weights alone are **14.54 GiB per GPU**. The model cannot load at all. No tuning fixes
this, and the pre-authorised 0.90 → 0.85 deviation moves the wrong way. **The KV-pool axis
does not exist for this model on 24 GB cards.**

### 6.2 The mamba cache caps concurrency below the RUNBOOK's `max-num-seqs`

> `ValueError: max_num_seqs (256) exceeds available Mamba cache blocks (114). Each decode
> sequence requires one Mamba cache block, so CUDA graph capture cannot proceed.`

Each decode sequence needs one constant-size DeltaNet state block, and only **114** fit.
The RUNBOOK's `--max-num-seqs 128` exceeds that cap, and `calibrate.py` — which never
passes `max_num_seqs` and so inherits vLLM's default of 256 — cannot run at all without
editing shipped code.

**v1 requirement:** mamba-cache concurrency caps must enter the simulator's **admission
logic**. `Cfg.max_num_seqs` is currently a flat limit; for a hybrid model the real limit is
`min(max_num_seqs, mamba_blocks)`, and mamba blocks compete with attention blocks for the
same pool.

### 6.3 The 784-token block size breaks the simulator's core assumption

vLLM forces the attention block size up to **784 tokens** so that the attention page is at
least as large as the mamba page ("Padding mamba page size by 0.13% to ensure that mamba
page size and attention page size are exactly equal"). `simulator.py` hard-codes
`Cfg.block_size = 16` with no CLI override — a **49× granularity mismatch** in exactly the
KV and prefix-cache accounting this experiment measures.

**This is why the methodology was validated on standard attention instead.** Any MISS on
Qwen3.8 would have been uninterpretable: there would be no way to separate a simulator
physics error from a broken block-size assumption. One variable at a time.

**v1 requirements, in priority order:**
1. **`block_size` must become a parameter** — CLI-settable and read from the engine, not
   hard-coded to 16.
2. **DeltaNet constant-state layers need their own term in the step model.** The current
   `c_kv × kv_tokens_read` assumes every layer's KV read grows with context. Here only 16
   of 64 layers do; the other 48 read a constant-size state that scales with **batch**, not
   context. The fix the RUNBOOK anticipates — splitting `c_kv` into a context-growing
   attention part and a batch-growing constant part — is confirmed necessary.
3. **Mamba-cache concurrency caps must enter admission logic** (§6.2).

---

## 7. Deviations from the protocol, and why

| # | Deviation | Authority |
|---|---|---|
| 1 | **Model switched** `Qwen3.8-27B-FP8` → `Qwen3-32B-AWQ` | RUNBOOK fallback ("misbehaves or runs out of memory"); infeasibility established in §6; approved before any prediction |
| 2 | **`gpu-memory-utilization` 0.90 → 0.85** for A and B | Pre-authorised self-service deviation; RUNBOOK's documented remedy for OOM on config A. Actual N recorded (§2) |
| 3 | **Trace vocabulary re-derived twice** | Approved both times; shipped vocabulary would have aborted the run (§5.1). Generator logic, seed and CLI args never changed |
| 4 | **`sim_A`/`sim_B` regenerated once** at N=5450 | Approved. See §8 |
| 5 | Environment fixes (§9) | Plumbing to make vLLM run on this box; applied identically to calibration and all three configs |

**Not needed:** axis B' (prefix caching works, §2); C@0.70 (C@0.60 loads cleanly and the
largest request is 5,167 tokens against a 39,040-token pool).

---

## 8. Freeze discipline

Predictions were committed **before** any real benchmark run, and neither `sim_*.json` nor
`perf.json` was touched afterwards.

```
322cb24  Pristine repo state before validation run (as shipped)
f3b598b  workload: single-token VOCAB for Qwen3.8 tokenizer; regenerate trace
80feb97  workload: re-derive VOCAB from Qwen3-32B-AWQ tokenizer; regenerate trace
16c838c  calibrate: perf.json for Qwen3-32B-AWQ TP=2 (frozen before predictions)
ceb637c  PREDICTIONS: sim_A/B/C generated and frozen before any real benchmark run
4a454c1  CORRECTED PREDICTIONS: sim_A/sim_B regenerated at N=5450; freeze now absolute
```

`ceb637c` was superseded by `4a454c1` once and only once. The reason, recorded at the
time and worth restating:

> The freeze rule protects prediction-precedes-measurement, and no measurement existed
> yet. `bench.py` had never executed and no `real_*.json` existed. The only thing that
> changed was an input parameter — `N_A` — which had been read off the single config-A
> startup that survived at 0.90, a setting the box cannot run reproducibly. Changing an
> input parameter to match the config that will actually run is a **corrected prediction,
> not tuning.**

The superseded N=5738 prediction remains in git history at `ceb637c`. After `4a454c1` the
freeze was absolute; no further changes were made, and every MISS above is reported as
found.

---

## 9. Environment fixes required to run vLLM 0.28.0 on this box

Applied identically to calibration and all three configs (`scripts/env.sh`, captured as
`results/logs/env_used.sh`), so they cannot bias a comparison between configs.

1. **venv on `PATH`** — FlashInfer's JIT needs the `ninja` binary; invoking
   `.venv/bin/python` directly instead of activating hides it.
2. **`VLLM_USE_FLASHINFER_SAMPLER=0`** — FlashInfer 0.6.16's JIT sampling kernel calls
   `cub::BlockAdjacentDifference::FlagHeads`, **removed in CCCL 3.x** (shipped with CUDA
   13.0), so it fails to compile. vLLM's PyTorch-native top-k/top-p sampler is used
   instead. The benchmark runs greedy (`temperature=0.0`), and the README already folds
   sampling cost into constant `a`.
3. **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** — vLLM's KV budget does not cover
   CUDA-graph private pools or non-torch allocations, so the process overshoots its own
   `gpu-memory-utilization` target and large decode batches hit fragmentation.

---

## 10. What this run says about the v0 hypothesis

The hypothesis — *an offline replay simulator can predict the effect of a vLLM config
change within 15 points* — is **not supported** by this run, but the failure is
informative and localised:

- **Aggregate throughput on the caching axis is already there** (4.5 pt gap). The step
  model's bulk arithmetic is sound.
- **Median latency on the baseline config is already there** (e2e_p50 −2.3%, throughput
  +0.9%). The engine's steady-state behaviour is well captured.
- **Tail latency is not**, and the cause is concentrated in one place: prefix-cache blocks
  become reusable only at request completion (§4.1), which inflates prefill work by 1.77×
  and manufactures queueing that the engine never experiences.
- **KV-pool pressure is not**, and here the model is qualitatively wrong (§4.3): it has no
  coupling between pool size and cache retention, so it cannot represent the
  evict-then-recompute behaviour that dominates config C. Since the README names
  eviction/cache-size comparison as the **v1 product axis**, this is the blocking defect,
  ahead of anything on the current simplification list.

The two highest-value fixes are therefore **not** the ones the README anticipates. Ranked
by evidence from this run:

1. Publish prefix-cache blocks when they are **computed**, not when the request finishes.
2. Couple the prefix cache to the block pool so eviction pressure produces recompute.
3. Make preemption a routine scheduling outcome rather than an emergency branch.
4. Add the TP communication term (§4.2) — worth ~16–23% on saturated configs.
5. Parameterise `block_size` and split `c_kv` for hybrid models (§6) before Qwen3.8 can be
   a target at all.
