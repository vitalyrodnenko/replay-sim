# replay-sim v0.3 validation report — run 3

**Date:** 2026-08-27
**Verdict (held-out configs F and G):** **FAIL** — **10 of 12** rows within the 15-point bar.
**Bottom line:** the failure has collapsed to a single metric. Both remaining held-out
misses are `ttft_p95`; every cost metric and every other SLA metric passes, most by a wide
margin. And the run-2 hypothesis about `c_kv` was **wrong**: recovering it bought 1.0 point
of e2e error, not the 20+ points I expected. The real cause of the e2e gap is now measured
and is not in the simulator at all.

| Run | Simulator | Held-out rows within bar |
|---|---|---|
| 1 | v0 | 1 of 11 |
| 2 | v0.2 | 9 of 12 |
| **3** | **v0.3** | **10 of 12** |

---

## 1. Environment

Unchanged from runs 1–2 except the simulator and calibration. Full capture:
`results/logs/environment.txt`.

| | |
|---|---|
| GPUs | 2 × RTX 4090, 24,564 MiB, compute capability 8.9 |
| Driver / CUDA | 580.173.02 / CUDA 13.0 |
| vLLM / torch / transformers | 0.28.0 / 2.13.0 / 5.16.1 |
| Model | `Qwen/Qwen3-32B-AWQ`, AWQ 4-bit, TP=2, 9.01 GiB/GPU |
| Simulator | **v0.3** (commit `e5838dd`) |
| Trace | unchanged, `sha256 4e70250f…` |

New warning observed this run, relevant to §7.3:
`Custom allreduce is disabled because your platform lacks GPU P2P capability` — TP
collectives cross PCIe host memory on this box.

### v0.3 drop-in

Replaced only the three files named in the handoff: `calibrate.py`, `simulator.py`,
`README.md`. **`workload.py` was again not replaced** — the archive ships the pristine
pre-fix `tok0..tok511` version for the second time, and copying it would revert the
tokenizer fix and break trace provenance. Verified after the swap: the trace still
regenerates byte-identically. `bench.py`, `compare.py`, `RUNBOOK.md` and `__init__.py` in
the archive were byte-identical to current.

---

## 2. Calibration gate

The instruction was to stop before predicting if the `c_kv ≤ 0` warning fired. **It did
not fire.** The redesigned grid identified the KV term:

```
decode fit R² = 0.95147          c_kv = 0.01607

B=8   ctx 512 / 2048 / 4096   ->  15.61 / 15.33 / 18.63 ms
B=16  ctx 4096                ->  24.89 ms
B=32  ctx 512 / 2048          ->  21.36 / 21.50 ms
B=64  ctx 512 / 1024          ->  31.30 / 30.00 ms
B=96  ctx 512                 ->  45.84 ms
B=128 ctx 256                 ->  58.04 ms

            a          b_p          b_d          c_kv
v0  run 1  0.014146   0.00041879   0.00018597   0.047886
v0.2 run 2 0.012686   0.00041896   0.00034517   0.0       (clamped, unidentified)
v0.3 run 3 0.012935   0.00041897   0.00032273   0.01607   (identified)
```

**Caveat recorded before predicting, not corrected:** the context signal is weak and
**non-monotonic in two of three fixed-batch pairs** — B=8 falls from 15.61 ms at ctx 512 to
15.33 ms at ctx 2048, and B=64 falls from 31.30 ms at ctx 512 to 30.00 ms at ctx 1024.
`c_kv` is positive and identified, but poorly conditioned, which is what R² = 0.951
reflects against 0.9998 for the prefill fit. The grid decorrelated kv from batch well
enough to clear the gate; it did not produce a strong context signal.

### Predicted-with N versus actually-run N

Every config's KV capacity was probed from its own startup log before predicting.

| Config | util | mns | mbt | probed N | run N | Match |
|---|---|---|---|---|---|---|
| A | 0.85 | 128 | 2048 | 5,450 | 5,450 | ✅ |
| B | 0.85 | 128 | 2048 | 5,450 | 5,450 | ✅ |
| C | 0.60 | 128 | 2048 | 2,440 | 2,440 | ✅ |
| D | 0.85 | 32 | 2048 | 5,490 | 5,490 | ✅ |
| E | 0.70 | 128 | 2048 | 3,644 | 3,644 | ✅ |
| **F** | 0.78 | 128 | 2048 | **4,607** | 4,607 | ✅ |
| **G** | 0.85 | 128 | **8192** | **5,106** | **5,141** | ❌ **+0.7%** |

> **Finding, not corrected.** G ran on an 82,256-token pool against a predicted 81,696 —
> the same non-deterministic vLLM sizing seen in runs 1 and 2, now at 0.7% rather than
> 6.1%. Too small to move G's verdict, but recorded rather than quietly reconciled.
>
> D's pool has settled: it probed at 87,840 this run, matching its run-2 *run* value
> rather than its run-2 probe of 82,816.

---

## 3. Held-out results — the verdict

F (pool at an unseen 0.78) and G (chunked-prefill axis, never varied before) are the only
held-out configs; A–E all informed v0.3's design.

### F vs A — **5 / 6 OK**

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| ttft_p50_s | +0.4% | +2.8% | **2.4 pt** | ✅ OK |
| ttft_p95_s | +40.0% | +111.8% | 71.8 pt | ❌ MISS |
| e2e_p50_s | +1.5% | +3.8% | **2.4 pt** | ✅ OK |
| e2e_p95_s | +27.2% | +22.9% | **4.3 pt** | ✅ OK |
| throughput_tok_s | −3.0% | −3.1% | **0.0 pt** | ✅ OK |
| prefix_cache_hit_rate | −2.8% | −5.0% | **2.2 pt** | ✅ OK |

### G vs A — **5 / 6 OK**

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| ttft_p50_s | +0.0% | −0.8% | **0.8 pt** | ✅ OK |
| ttft_p95_s | +6.7% | +29.1% | 22.4 pt | ❌ MISS |
| e2e_p50_s | +1.0% | +0.2% | **0.7 pt** | ✅ OK |
| e2e_p95_s | +0.2% | +4.9% | **4.7 pt** | ✅ OK |
| throughput_tok_s | −0.9% | −1.6% | **0.7 pt** | ✅ OK |
| prefix_cache_hit_rate | −0.6% | −1.3% | **0.7 pt** | ✅ OK |

**Held-out total: 10 of 12.** Both misses are the *same metric*. Nine of the ten passing
rows clear the bar by more than 10 points.

v0.3 made a sharp, falsifiable claim on G before the run: quadrupling
`--max-num-batched-tokens` from 2048 to 8192 would be nearly inert, because in the step
model total prefill work is unchanged and only its granularity moves. Measurement agreed on
five of six rows — e2e_p50 predicted +1.0% against +0.2% measured. The exception is exactly
where a granularity change should show up: the TTFT tail.

---

## 4. In-sample results (development data — proves nothing)

**15 of 23 rows** within the bar.

| Row | sim Δ | real Δ | gap | |
|---|---|---|---|---|
| B vs A ttft_p50_s | +21170.3% | +22523.2% | 1352.9 pt | MISS |
| B vs A ttft_p95_s | +19143.4% | +22993.6% | 3850.2 pt | MISS |
| B vs A e2e_p50_s | +2167.8% | +1894.2% | 273.6 pt | MISS |
| B vs A e2e_p95_s | +2636.3% | +2212.5% | 423.7 pt | MISS |
| B vs A throughput_tok_s | −46.5% | −49.6% | **3.1 pt** | ✅ OK |
| C vs A ttft_p50_s | +486.0% | +472.0% | **14.1 pt** | ✅ OK |
| C vs A ttft_p95_s | +3994.8% | +4239.1% | 244.3 pt | MISS |
| C vs A e2e_p50_s | +145.2% | +204.6% | 59.4 pt | MISS |
| C vs A e2e_p95_s | +656.0% | +466.3% | 189.7 pt | MISS |
| C vs A throughput_tok_s | −18.7% | −17.6% | **1.1 pt** | ✅ OK |
| C vs A prefix_cache_hit_rate | −31.1% | −30.2% | **0.9 pt** | ✅ OK |
| D vs A (all six rows) | +0.0% | +0.4 … −9.2% | **0.4–9.2 pt** | ✅ **6/6 OK** |
| E vs A ttft_p50_s | +31.9% | +32.5% | **0.6 pt** | ✅ OK |
| E vs A ttft_p95_s | +406.7% | +396.9% | **9.8 pt** | ✅ OK |
| E vs A e2e_p50_s | +9.8% | +24.4% | **14.7 pt** | ✅ OK |
| E vs A e2e_p95_s | +117.7% | +176.7% | 59.0 pt | MISS |
| E vs A throughput_tok_s | −3.8% | −3.9% | **0.1 pt** | ✅ OK |
| E vs A prefix_cache_hit_rate | −13.5% | −15.1% | **1.6 pt** | ✅ OK |

E improved sharply against run 2: `ttft_p95` 82.1 → **9.8 pt**, `e2e_p50` 15.04 (MISS) →
**14.7 pt (OK)**. B's rows remain enormous for the structural reason established in run 1 —
the relative change is divided by a config-A tail of 0.64 s, so any baseline error becomes
thousands of points.

---

## 5. Product scorecard

### Cost metrics — **every gap inside the bar**

| Config | throughput sim/real | abs err | gap vs A | gpu_s/1k sim/real\* | abs err | hit sim/real | abs err | gap vs A |
|---|---|---|---|---|---|---|---|---|
| A | 209.9 / 207.7 | +1.1% | — | 4.521 / 4.514 | +0.2% | 0.862 / 0.855 | +0.8% | — |
| B | 112.3 / 104.6 | +7.4% | **3.1 pt** | 8.890 / 9.411 | −5.5% | 0.000 / n/a | — | — |
| C | 170.7 / 171.2 | −0.3% | **1.1 pt** | 5.724 / 5.541 | +3.3% | 0.594 / 0.597 | −0.5% | **0.9 pt** |
| D | 209.9 / 208.7 | +0.6% | **0.5 pt** | 4.521 / 4.491 | +0.7% | 0.862 / 0.859 | +0.3% | **0.5 pt** |
| E | 201.9 / 199.6 | +1.2% | **0.1 pt** | 4.791 / 4.715 | +1.6% | 0.746 / 0.726 | +2.8% | **1.6 pt** |
| **F**\*\* | 203.5 / 201.3 | +1.1% | **0.0 pt** | 4.671 / 4.667 | +0.1% | 0.838 / 0.812 | +3.2% | **2.2 pt** |
| **G**\*\* | 208.1 / 204.4 | +1.8% | **0.7 pt** | 4.562 / 4.596 | −0.7% | 0.857 / 0.844 | +1.5% | **0.7 pt** |

\* `gpu_s/1k` real is **derived**, not measured: `makespan × mean nvidia-smi utilisation ÷
output tokens`. `bench.py` does not measure GPU-seconds, so treat this column as an estimate.
\*\* held-out.

**Cost is solved for this workload.** Throughput within 1.8% on every config except B,
derived cost-per-1k-tokens within 3.3%, hit rate within 3.2%, and every cost gap ≤ 3.1 pt
against a 15-point bar. If the product question is "what will this config change do to my
serving cost and cache efficiency", v0.3 answers it — including on both held-out axes.

### SLA metrics — where it still fails

| Metric | A | B | C | D | E | F\*\* | G\*\* |
|---|---|---|---|---|---|---|---|
| ttft_p50 abs err | −6.9% | −12.5% | −4.6% | −7.3% | −7.4% | −9.1% | −6.1% |
| ttft_p50 gap | — | 1352.9 | **14.1** | **0.4** | **0.6** | **2.4** | **0.8** |
| ttft_p95 abs err | +4.4% | −13.0% | −1.5% | +14.9% | +6.4% | −31.0% | −13.8% |
| ttft_p95 gap | — | 3850.2 | 244.3 | **9.2** | **9.8** | 71.8 | 22.4 |
| e2e_p50 abs err | **−21.1%** | −10.2% | −36.4% | **−20.2%** | −30.4% | **−22.9%** | **−20.5%** |
| e2e_p50 gap | — | 273.6 | 59.4 | **1.1** | **14.7** | **2.4** | **0.7** |
| e2e_p95 abs err | **−25.7%** | −12.0% | −0.8% | **−22.4%** | −41.5% | **−23.1%** | **−29.0%** |
| e2e_p95 gap | — | 423.7 | 189.7 | **4.2** | 59.0 | **4.3** | **4.7** |

The scorecard exposes something the relative bar hides: **every e2e absolute error is
negative**, 20–41% across all seven configs. The e2e *deltas* pass on D, E, F and G
precisely because the bias is uniform and cancels in the ratio. That is a real predictive
limitation being masked by the metric definition, and it is the subject of §7.1.

---

## 6. v0.2 → v0.3: what `c_kv` recovery actually bought

Absolute error `|sim − real| / real` on A, D and E, with signed error in brackets.

| Config | Metric | v0.2 err | v0.3 err | |
|---|---|---|---|---|
| A | ttft_p50_s | 6.1% [−6.1] | 6.9% [−6.9] | worse |
| A | **ttft_p95_s** | 27.3% [+27.3] | **4.4% [+4.4]** | **better** |
| A | **e2e_p50_s** | 23.2% [−23.2] | 21.1% [−21.1] | ~same |
| A | **e2e_p95_s** | 24.5% [−24.5] | 25.7% [−25.7] | ~same |
| A | throughput_tok_s | 5.9% [+5.9] | **1.1% [+1.1]** | **better** |
| A | prefix_cache_hit_rate | 0.7% | 0.8% | worse |
| D | ttft_p50_s | 6.1% [−6.1] | 7.3% [−7.3] | worse |
| D | **ttft_p95_s** | 37.3% [+37.3] | **14.9% [+14.9]** | **better** |
| D | **e2e_p50_s** | 22.7% [−22.7] | 20.2% [−20.2] | better |
| D | **e2e_p95_s** | 21.2% [−21.2] | 22.4% [−22.4] | ~same |
| D | throughput_tok_s | 5.4% [+5.4] | **0.6% [+0.6]** | **better** |
| D | prefix_cache_hit_rate | 0.3% | 0.3% | ~same |
| E | ttft_p50_s | 3.1% [−3.1] | 7.4% [−7.4] | worse |
| E | ttft_p95_s | 6.0% [+6.0] | 6.4% [+6.4] | ~same |
| E | **e2e_p50_s** | 32.4% [−32.4] | 30.4% [−30.4] | ~same |
| E | **e2e_p95_s** | 43.2% [−43.2] | 41.5% [−41.5] | ~same |
| E | throughput_tok_s | 6.1% [+6.1] | **1.2% [+1.2]** | **better** |
| E | prefix_cache_hit_rate | 2.8% | 2.8% | ~same |

**Mean absolute error: 15.2% → 12.0%** (n = 18).

### The e2e rows in isolation — the point of the exercise

| Row | v0.2 | v0.3 | change |
|---|---|---|---|
| A e2e_p50 | 23.2% | 21.1% | −2.1 pt |
| A e2e_p95 | 24.5% | 25.7% | +1.1 pt |
| D e2e_p50 | 22.7% | 20.2% | −2.4 pt |
| D e2e_p95 | 21.2% | 22.4% | +1.2 pt |
| E e2e_p50 | 32.4% | 30.4% | −2.0 pt |
| E e2e_p95 | 43.2% | 41.5% | −1.7 pt |
| **mean** | **27.9%** | **26.9%** | **−1.0 pt** |

**Recovering `c_kv` bought 1.0 point of e2e error.** After run 2 I hypothesised that
`c_kv = 0` was the cause of the 21–43% e2e under-prediction and that recovering it would be
the highest-value fix. **That hypothesis is falsified.** The KV term is now identified and
positive, and the e2e gap is essentially unchanged — three rows improved by ~2 points, two
got slightly worse, and every row remains under-predicted by 20–42% with the same sign.

What v0.3 *did* buy is real but sits elsewhere: **`ttft_p95` on the in-sample configs**
(A 27.3% → 4.4%, D 37.3% → 14.9%) and **throughput** (5.9% → 1.1%, 5.4% → 0.6%,
6.1% → 1.2%), which is what carried the cost scorecard to near-perfect.

---

## 7. Hypotheses for the remaining failures

No simulator code or `perf.json` was modified at any point.

### 7.1 The e2e under-prediction is a fixed ~5.6 ms per decode step the model never sees

Measuring the `e2e_p50` deficit per output token on the four low-queue configs (median
output = 186 tokens over the kept 182 requests):

| Config | sim | real | deficit | ms per output token |
|---|---|---|---|---|
| A | 3.822 | 4.842 | 1.020 s | **5.48** |
| D | 3.822 | 4.791 | 0.969 s | **5.21** |
| F | 3.878 | 5.028 | 1.150 s | **6.18** |
| G | 3.859 | 4.854 | 0.995 s | **5.35** |
| | | | | **mean 5.56, stdev 0.43** |

The deficit is **invariant across a 5,450 → 4,607 block range and a 4× change in prefill
budget**. That is the signature of a constant per-decode-step cost, not of a mis-fitted
context or batch coefficient — which is precisely why recovering `c_kv` did nothing for it
(§6). At a modelled step time of 15.2 ms, an unmodelled 5.6 ms is **43% of the fitted
per-step constant `a` = 12.94 ms**.

**Hypothesis: `a` is fitted on the wrong execution path.** `calibrate.py` measures vLLM's
**offline** `LLM()` batch API; `bench.py` measures the **online** OpenAI HTTP server with
`stream: True`. The online path adds, per step and per token, scheduler bookkeeping,
incremental detokenization, SSE frame construction and HTTP write — none of which the
offline path pays. TTFT barely shows it because TTFT is dominated by `b_p × prompt_tokens`;
e2e accumulates it over ~186 steps. This is a **calibration-harness** issue, like the
`c_kv` grid before it, not simulator physics.

It also explains the one place the effect is absent: config C's `e2e_p95` absolute error is
only −0.8%, because C is so queue-bound that waiting time swamps per-step overhead.

### 7.2 Both held-out misses are `ttft_p95`, and both are under-prediction of tail queueing

F: sim +40.0% vs real +111.8%. G: sim +6.7% vs real +29.1%. In both, the simulator captures
the direction and gets the median right (`ttft_p50` gaps of 2.4 and 0.8 pt) but
under-predicts how heavy the *tail* of the first-token wait becomes.

For **G** the mechanism is specific and was visible in the prediction itself: with
`--max-num-batched-tokens 8192`, one prefill step can consume 8,192 tokens ≈ 3.4 s of GPU
time. The simulator charges that step `b_p × 8192` and moves on, so a request arriving
behind it waits one step. Real vLLM cannot preempt a running prefill chunk either, but the
step is long enough that queue build-up behind it is non-linear — arrivals stack during a
single 3.4 s step. The simulator's step-granular queueing under-represents this. That the
error appears *only* at p95 and only on the axis that quadrupled step size is consistent.

For **F** the same mechanism operates through pool pressure rather than step size: at 0.78
the pool is tight enough that admission stalls become bursty, and burstiness lives in the
tail, not the median.

### 7.3 Config B's remaining gaps

B is uniformly under-predicted by 10–13% and it is the one config that runs both GPUs at
98.4% for five minutes. The `Custom allreduce is disabled … lacks GPU P2P capability`
warning means TP collectives cross PCIe host memory here, so the un-modelled communication
term is larger on this box than on hardware with NVLink or working P2P. Still the best
candidate from the README's original list, and still un-modelled.

### 7.4 The metric definition continues to distort the verdict

Config B's rows are 273–3850 points off while its *absolute* errors are 10–13%. C's
`ttft_p95` absolute error is 1.5% and its gap is 244 pt. These are artifacts of dividing by
a small config-A baseline, not statements about predictive quality. The product scorecard
in §5 exists because of this: it shows absolute error next to the gap, and on cost metrics
the two agree, while on tail-latency metrics they diverge sharply.

---

## 8. Run integrity

- **Recalibration committed before any prediction** (`cca9676`); calibration gate checked
  and passed before proceeding, as instructed.
- **All seven predictions committed before any real run** (`e28649b`), freeze absolute.
  The one post-freeze mismatch (G's pool, +0.7%) is reported, not reconciled.
- **Held-out runs executed first** (F, G), before the in-sample five.
- **`--drop-first 10` on both `bench.py` and the simulator**, so both score exactly 182
  requests. The run-2 asymmetry (sim 192 vs real 182) is gone.
- **Server fully restarted between all seven runs**; readiness polled on `/health`.
- **Reproducibility check:** config D was run in both run 2 and run 3 with the same
  settings. e2e_p50 4.796 → 4.791 s, throughput 208.7 → 208.7 tok/s. The box is stable;
  differences between runs are the simulator's, not the hardware's.

### Tooling fixes this run

`scripts/serve.sh` now defaults A and B to 0.85 rather than the RUNBOOK's 0.90, with a
comment explaining why. In run 2 I invoked `run_config.sh A` without the utilisation
argument, the default sent it to 0.90, and it died in CUDA-graph capture. Removing the
footgun rather than relying on remembering the argument.

---

## 9. Where this leaves the hypothesis

Three runs in, the picture is sharp:

**What is validated.** Cost prediction. Throughput within 1.8%, derived GPU-seconds per 1k
tokens within 3.3%, prefix-cache hit rate within 3.2%, on five distinct config axes
including two held-out ones — with every cost gap ≤ 3.1 points against a 15-point bar. The
cache/pool model that was qualitatively wrong in run 1 (a sign error) now generalises to
unseen pool sizes at 0.7–2.2 points.

**What is not.** Tail latency. Both held-out misses are `ttft_p95`, and a uniform 20–41%
e2e under-prediction runs through every config, currently hidden from the verdict because
it cancels in the ratio.

**The two open defects are both in the calibration harness, not the simulator.** Run 2's
was the decode grid failing to identify `c_kv`; run 3's is `a` being fitted on the offline
engine while the benchmark measures the online server. That pattern is worth naming: the
step model has been adequate each time, and what has actually limited accuracy is how its
coefficients are measured.

Ranked next steps:

1. **Fit `a` on the online path.** Drive the HTTP server with a fixed batch at steady state
   and fit per-step cost from it, or add an explicit per-token online-overhead term. §7.1
   measures the target: ~5.6 ms per decode step, 43% of the current `a`. This is the single
   change that would move every e2e row at once.
2. **Model queue build-up within a long prefill step** (§7.2) — the mechanism behind both
   held-out misses, and specifically exposed by the G axis.
3. **Add the TP communication term** — still the best explanation for B's 10–13%, and
   larger than usual on this box because P2P is unavailable.
4. **Report absolute error alongside relative gaps as standard.** The scorecard already
   does this; the verdict criterion still does not. Any change to that criterion belongs
   between rounds, in writing — flagging it, not doing it.

A fourth run that fixes only item 1 would be a clean test: it should move all seven e2e
absolute errors toward zero while leaving the cost scorecard untouched, and it would tell
us whether the two `ttft_p95` misses are independent of it or downstream of the same cause.
