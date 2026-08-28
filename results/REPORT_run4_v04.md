# replay-sim v0.4 validation report — run 4

**Date:** 2026-08-28
**Scope:** one change only — the per-step constant `a` refitted on the online path.
**Pre-registered hypotheses:** (i) **CONFIRMED**, (ii) **CONFIRMED** (one threshold
clause mis-specified, see §4.2), (iii) **recorded: the F/G tail misses are
independent of `a`**.
**Verdict on the 15-point bar (unchanged criterion):** **FAIL** — F/G **10 of 12**,
unchanged; in-sample **13 of 23**, down from 15.

**Bottom line.** Run 3's §7.1 hypothesis is confirmed on its own terms and then
some: refitting `a` against the HTTP server closed **83%** of the e2e deficit
(5.56 → 0.96 ms per output token) and cut mean e2e absolute error from **22.6%
to 9.3%**, with the cost scorecard intact. But the calibration that produced it
also falsified the *mechanism* run 3 proposed. The online overhead is **not a
constant per step**: it grows with batch and context, from +0.2 ms at B=1 to
+12.0 ms at B=32/ctx=2048. A single `a` is the wrong shape for it, and the
15-point verdict count went **down** while absolute error improved almost
everywhere — the metric distortion §7.4 warned about, now acting on this run's
own result.

| Run | Simulator | Held-out rows in bar | Mean abs err, all metrics |
|---|---|---|---|
| 1 | v0 | 1 of 11 | — |
| 2 | v0.2 | 9 of 12 | 15.2% (A/D/E subset) |
| 3 | v0.3 | 10 of 12 | 11.6% |
| **4** | **v0.4 hybrid** | **10 of 12** (re-prediction) | **7.0%** |

---

## 1. What this run is, and what it is not

**It makes no new real measurements of A–G.** The `real_*.json` files from run 3
are reused as-is. Run 4 is a **re-prediction against already-seen
measurements**. It tests the three hypotheses frozen in
`results/PREDICTIONS_run4.md` (commit `613fc13`) and nothing else.

F and G were genuinely held out in run 3. **They are not held out in run 4** —
their measurements were known to the person choosing this change. The 10-of-12
figure below is reported for continuity with runs 1–3; it is *not* evidence of
generalisation. **Any claim beyond hypotheses (i)–(iii) needs a fresh held-out
config in a later run.** §9 names the one that would settle it.

### What changed

| | |
|---|---|
| `perf.json` `a` | 12.935 ms → **16.111 ms** (+3.176), refitted on the online path |
| `perf.json` `b_p`, `b_d`, `c_kv` | **unchanged**, carried from the v0.3 offline fit |
| `calibrate.py` | new `--mode online`; offline mode byte-identical |
| `simulator.py` | `Perf.load` ignores provenance keys. **No physics change** |
| `scripts/calibrate_online.sh` | new: serve A → wait → calibrate → stop |
| trace, config definitions, block-pool figures, `--drop-first 10`, 15-pt bar | **unchanged from run 3** |

Config arguments for all seven re-predictions were verified equal, field by
field, to the `config` block recorded inside each run-3 `sim_*.json`. The only
input that differs is `perf.json`.

Environment is run 3's: 2 × RTX 4090, driver 580.173.02 / CUDA 13.0, vLLM
0.28.0 / torch 2.13.0, `Qwen/Qwen3-32B-AWQ` AWQ 4-bit TP=2. The calibration
server came up with a **KV pool of 87,200 tokens — identical to run 3's config
A**, so the online measurement is on the same engine state the predictions
assume.

---

## 2. The online calibration

Config-A server (`gpu-mem-util 0.85`, `max-num-seqs 128`,
`max-num-batched-tokens 2048`, prefix caching on), driven through the same
`httpx` streaming client `bench.py` uses. B streams of pinned output length
decode in lockstep, so the inter-token interval inside a window where all B are
resident *is* the engine step time. The window opens once the last stream is 64
tokens into its output and closes 8 tokens before the first stream finishes, so
every step inside it ran at batch exactly B. Prompts are unique per stream —
the server reported a prefix cache hit rate of **0.0%** throughout, matching the
offline fit's `enable_prefix_caching=False`.

**Reproducibility: 3 repeats per point agree to within 0.07 ms; the spread
across the B streams of a point is ≤ 0.01 ms.** This is a far cleaner
measurement than the offline decode grid it replaces, for the reason in §6.

| B | ctx | offline (run 3) | **online** | v0.3 model | online − model | implied `a` |
|---|---|---|---|---|---|---|
| 1 | 512 | 13.40 ms | **13.58** | 13.27 | +0.31 | 13.24 |
| 8 | 512 | 15.61 ms | **16.60** | 15.58 | +1.02 | 13.96 |
| 8 | 2048 | 15.33 ms | **18.28** | 15.78 | +2.50 | 15.44 |
| 32 | 512 | 21.36 ms | **26.39** | 23.53 | +2.86 | 15.80 |
| 32 | 2048 | 21.50 ms | **33.50** | 24.32 | +9.19 | 22.12 |

    a_online = 16.111 ms   (offline 12.935 ms, delta +3.176 ms)

Check point held out of the fit — B=16, ctx=3072, the trace's median prompt
length: online 26.36 ms, v0.3 model 18.89 ms, hybrid model 22.06 ms. **The
hybrid still under-predicts this point by 16.3%.**

### 2.1 Caveat recorded before predicting, not corrected

**The online overhead is not a constant per step.** The implied intercept runs
from 13.24 ms at B=1 to 22.12 ms at B=32/ctx=2048 — spread 8.88 ms, stdev
3.52 ms, *larger than the +3.18 ms correction itself*. The `calibrate.py` gate
(stdev > 25% of `a_online`) did **not** fire — 3.52 against a 4.03 threshold —
so the run proceeded as scoped. This was written into
`PREDICTIONS_run4.md` before any simulation was run, and is not corrected here.

---

## 3. Pre-registered hypothesis (i) — CONFIRMED

> All seven e2e absolute errors move toward zero; mean `|e2e err|` drops from
> ~27% to under 10%.

| Config | metric | real | v0.3 sim | err | v0.4 sim | err | toward 0 |
|---|---|---|---|---|---|---|---|
| A | e2e_p50 | 4.842 | 3.822 | −21.1% | **4.681** | **−3.3%** | ✅ |
| A | e2e_p95 | 7.534 | 5.601 | −25.7% | **6.664** | **−11.5%** | ✅ |
| B | e2e_p50 | 96.561 | 86.675 | −10.2% | **88.634** | **−8.2%** | ✅ |
| B | e2e_p95 | 174.225 | 153.258 | −12.0% | **157.494** | **−9.6%** | ✅ |
| C | e2e_p50 | 14.747 | 9.372 | −36.4% | **12.392** | **−16.0%** | ✅ |
| C | e2e_p95 | 42.663 | 42.343 | −0.8% | 40.450 | −5.2% | ❌ |
| D | e2e_p50 | 4.791 | 3.822 | −20.2% | **4.681** | **−2.3%** | ✅ |
| D | e2e_p95 | 7.221 | 5.601 | −22.4% | **6.664** | **−7.7%** | ✅ |
| E | e2e_p50 | 6.024 | 4.195 | −30.4% | **5.331** | **−11.5%** | ✅ |
| E | e2e_p95 | 20.848 | 12.192 | −41.5% | **16.254** | **−22.0%** | ✅ |
| F | e2e_p50 | 5.028 | 3.878 | −22.9% | **4.724** | **−6.0%** | ✅ |
| F | e2e_p95 | 9.260 | 7.123 | −23.1% | **8.537** | **−7.8%** | ✅ |
| G | e2e_p50 | 4.854 | 3.859 | −20.5% | **4.716** | **−2.8%** | ✅ |
| G | e2e_p95 | 7.901 | 5.611 | −29.0% | **6.672** | **−15.6%** | ✅ |

| Pre-registered measure | v0.3 | v0.4 | threshold | |
|---|---|---|---|---|
| Primary: mean \|e2e err\|, 7 configs × 2 metrics (n=14) | 22.58% | **9.26%** | < 10% | ✅ |
| Subset (run-3 §6 metric): A/D/E e2e (n=6) | 26.88% | **9.74%** | < 10% | ✅ |
| Secondary: rows moving toward zero | — | **13 of 14** | 14 of 14 | ⚠️ |

The one exception is the one run 3 predicted. §7.1 said config C's e2e_p95 was
already accurate *because* C is so queue-bound that waiting time swamps
per-step overhead — so a per-step correction has nothing to add there and can
only overshoot. It did: −0.8% → −5.2%. The mechanism, not just the aggregate,
behaved as described.

**All 14 rows are still negative.** The bias is smaller, not gone.

### 3.1 The deficit §7.1 measured

Run 3 measured a 5.56 ± 0.43 ms per-output-token e2e deficit on the four
low-queue configs, invariant across pool size and prefill budget, and named it
as the target.

| Config | v0.3 sim | v0.4 sim | real | v0.3 deficit | v0.4 deficit | v0.3 ms/tok | v0.4 ms/tok |
|---|---|---|---|---|---|---|---|
| A | 3.822 | 4.681 | 4.842 | 1.020 s | 0.161 s | 5.48 | **0.87** |
| D | 3.822 | 4.681 | 4.791 | 0.969 s | 0.110 s | 5.21 | **0.59** |
| F | 3.878 | 4.724 | 5.028 | 1.150 s | 0.304 s | 6.18 | **1.63** |
| G | 3.859 | 4.716 | 4.854 | 0.995 s | 0.138 s | 5.35 | **0.74** |
| | | | | | | **mean 5.56** | **mean 0.96** |

**83% of the deficit is gone**, from a single coefficient moved by 3.18 ms.
Run 3 named the right target and measured it correctly.

---

## 4. Pre-registered hypothesis (ii) — CONFIRMED, with one clause I mis-specified

> The cost scorecard is unchanged within noise.

| Config | tput sim/real | err v0.3 → v0.4 | gap vs A | gpu_s/1k sim / real\* | err | hit sim/real | err | gap vs A |
|---|---|---|---|---|---|---|---|---|
| A | 209.1 / 207.7 | +1.1% → **+0.7%** | — | 4.628 / 4.514 | +2.5% | 0.862 / 0.855 | +0.8% | — |
| B | 110.5 / 104.6 | +7.4% → **+5.6%** | **2.5 pt** | 9.032 / 9.411 | −4.0% | 0.000 / n/a | — | — |
| C | 171.8 / 171.2 | −0.3% → **+0.4%** | **0.3 pt** | 5.721 / 5.542 | +3.2% | 0.596 / 0.597 | −0.2% | **0.7 pt** |
| D | 209.1 / 208.7 | +0.6% → **+0.2%** | **0.5 pt** | 4.628 / 4.492 | +3.0% | 0.862 / 0.859 | +0.3% | **0.5 pt** |
| E | 200.8 / 199.6 | +1.2% → **+0.6%** | **0.1 pt** | 4.880 / 4.715 | +3.5% | 0.739 / 0.726 | +1.8% | **0.8 pt** |
| F | 202.5 / 201.3 | +1.1% → **+0.6%** | **0.1 pt** | 4.784 / 4.667 | +2.5% | 0.838 / 0.812 | +3.2% | **2.2 pt** |
| G | 207.3 / 204.4 | +1.8% → **+1.4%** | **0.7 pt** | 4.669 / 4.596 | +1.6% | 0.857 / 0.844 | +1.5% | **0.7 pt** |

\* real `gpu_s/1k` is **derived**, not measured: makespan × mean `nvidia-smi`
utilisation ÷ output tokens. Unchanged methodology from run 3.

### 4.1 The recorded risk did not materialise

I recorded before running that (ii) was at risk in the throughput column: `a`
enters every step, so raising it lengthens `gpu_busy` and `makespan`, and
throughput would be under-predicted if the online overhead is pipelined rather
than GPU-serialising.

**It did not happen — and the reason is worth keeping.** `gpu_busy` did rise as
predicted (A: 150.7 → 154.3 s, +2.4%), but `makespan` barely moved (158.8 →
159.4 s, +0.4%), because on six of seven configs the makespan is **arrival-bound**:
the trace's last arrival is at 156.0 s and the engine finishes shortly after.
Throughput is output tokens ÷ makespan, so a change that consumes GPU slack
without extending the critical path leaves it almost untouched. Every
throughput error moved *toward* zero. That slack is a property of this trace at
this load, not a general result.

### 4.2 One threshold clause was mis-specified, and B violates it

I wrote: *"every config's |throughput error| stays ≤ 5% (v0.3: ≤ 1.8% on six
configs, +7.4% on B)"*. Those two halves contradict each other — B started at
7.4%, so a ≤ 5% pass condition was unreachable for B no matter what the change
did. B came in at **+5.6%**, which improves on v0.3 by 1.8 points and violates
the literal clause. The defect is in my pre-registration, not in the result.
Recording it rather than quietly reading the clause as "≤ 5% or improved".

The other two clauses pass outright: every cost delta-gap vs A is ≤ **2.5 pt**
(threshold 5), and `prefix_cache_hit_rate` moved by at most **0.7 points**
absolute (threshold 1).

---

## 5. Pre-registered hypothesis (iii) — recorded: the tail misses are independent of `a`

> Record whether F/G `ttft_p95` gaps move, as evidence for or against their
> independence from this cause. No directional prediction was made.

| | v0.3 sim Δ | v0.4 sim Δ | real Δ | v0.3 gap | v0.4 gap | |
|---|---|---|---|---|---|---|
| F `ttft_p95` | +40.0% | +34.9% | +111.8% | 71.8 pt | **77.0 pt** | ❌ MISS both |
| G `ttft_p95` | +6.7% | +6.3% | +29.1% | 22.4 pt | **22.9 pt** | ❌ MISS both |

**Unmoved.** A 25% increase in the per-step constant changed F's gap by 5.2
points and G's by 0.5, both in the wrong direction, and neither comes close to
the bar. **This is evidence that the two tail misses are independent of the
per-step constant** and belong to the queue-build-up mechanism run 3 proposed
in §7.2 — the simulator charging one long prefill step and moving on, while
real arrivals stack non-linearly behind a step that can run 3.4 s at
`--max-num-batched-tokens 8192`. Item 2 on run 3's ranked list is now the
first item that has not been tested.

---

## 6. The calibration falsified run 3's *mechanism*, while confirming its target

Run 3 §7.1 proposed a **constant** per-decode-step cost the offline path does
not pay. The correction works — §3 — but the measurement says the shape is
wrong.

| B | ctx | offline | online | delta | ratio |
|---|---|---|---|---|---|
| 1 | 512 | 13.40 | 13.58 | +0.18 | 1.01× |
| 8 | 512 | 15.61 | 16.60 | +0.99 | 1.06× |
| 8 | 2048 | 15.33 | 18.28 | +2.95 | 1.19× |
| 32 | 512 | 21.36 | 26.39 | +5.03 | 1.24× |
| 32 | 2048 | 21.50 | 33.50 | +12.00 | 1.56× |

The gap grows with **both** batch and context. A constant `a` splits the
difference: it over-charges B=1 by 2.5 ms and under-charges B=32/ctx=2048 by
6.0 ms. That is exactly why §3's residual is not zero and why the B=16/ctx=3072
check point is still 16.3% low.

### 6.1 The offline decode grid was measuring almost nothing

Hold batch fixed and quadruple context:

| | offline | online |
|---|---|---|
| B=8, ctx 512 → 2048 | **−0.28 ms** | **+1.68 ms** |
| B=32, ctx 512 → 2048 | **+0.14 ms** | **+7.11 ms** |

Run 3 §2 flagged the offline decode fit as non-monotonic in two of three
fixed-batch pairs, with R² 0.951 against 0.9998 for prefill, and recorded that
`c_kv` was "positive and identified, but poorly conditioned". The online
measurement resolves that: the context signal is real, monotonic, and large —
the *offline harness* could not see it.

The reason is in `calibrate.py`'s offline decode step, unchanged since v0:

```python
step = (total - (a_const + b_p * B * C)) / 64
```

At B=32, ctx=2048 that subtracts a **modelled** prefill of ~27.5 s from a
measured total, then divides the remainder by 64. A 5% error in the prefill
model — itself fitted on *single-sequence* prefill — puts ±21 ms per step into
the residual. The decode signal being fitted is smaller than the error bar of
the quantity subtracted from it. The online method never forms that difference:
it times steady-state decode directly, in a window where no prefill is running,
and reproduces to 0.07 ms.

**So both of run 3's open defects, and the one before them, are the same
defect**: the step model was fine; the harness measuring its coefficients was
not. Run 2's decode grid could not identify `c_kv`. Run 3's `a` was fitted on
the wrong execution path. Run 4 finds that the same offline harness also
flattened `b_d` and `c_kv` — and those are still frozen at the flattened values
in this run's `perf.json`, by scope.

---

## 7. The verdict criterion went the other way

Absolute error improved almost everywhere:

| Metric | mean \|err\| v0.3 | v0.4 | change |
|---|---|---|---|
| ttft_p50_s | 7.7% | **5.0%** | −2.7 pt |
| ttft_p95_s | 12.1% | 14.9% | **+2.8 pt** |
| e2e_p50_s | 23.1% | **7.2%** | −15.9 pt |
| e2e_p95_s | 22.1% | **11.3%** | −10.7 pt |
| throughput_tok_s | 1.9% | **1.4%** | −0.6 pt |
| prefix_cache_hit_rate | 1.5% | **1.3%** | −0.2 pt |
| **all metrics (n=41)** | **11.6%** | **7.0%** | **−4.7 pt** |

The 15-point relative bar went down: **25 of 35 rows → 23 of 35.**

| | v0.3 | v0.4 |
|---|---|---|
| F, G (held out in run 3 only) | 10 / 12 | **10 / 12** |
| In-sample A–E | 15 / 23 | **13 / 23** |

Two rows crossed the bar the wrong way — C `ttft_p50` 14.1 → 20.7 pt and E
`ttft_p95` 9.8 → 16.3 pt — while the e2e delta gaps improved enormously:

| Row | v0.3 gap | v0.4 gap |
|---|---|---|
| B e2e_p95 | 423.7 | **50.8** |
| B e2e_p50 | 273.6 | **100.8** |
| C e2e_p95 | 189.7 | **40.7** |
| C e2e_p50 | 59.4 | **39.8** |
| E e2e_p95 | 59.0 | **32.8** |
| E e2e_p50 | 14.7 | **10.5** |

And C's `ttft_p95` gap went 244.3 → **804.0** while its absolute error went
−1.5% → −10.8%: the ratio is taken against config A's `ttft_p95` of 0.67 s, so
a 33 ms improvement in A's own prediction moves C's *gap* by 560 points.

This is §7.4 of run 3, now acting on run 4's own headline. **A change that cut
mean absolute error by 40% is scored as a regression by the verdict
criterion.** The criterion is unchanged here because the run's scope forbade
touching it; run 3 already flagged that any change to it belongs between
rounds, in writing. This run is the evidence for making that change.

One scheduling side effect, recorded: config C's simulated preemptions fell
from 16 to 8. Slower steps shift the interleaving of arrivals against
admissions. No other config's preemption count changed.

---

## 8. Run integrity

- **Calibration committed before any prediction** (`613fc13`), together with
  `PREDICTIONS_run4.md` stating hypotheses (i)–(iii), their numeric thresholds,
  and the non-constant-intercept caveat. No simulation had been run at that
  commit.
- **All seven predictions committed before any comparison** (`8a4a02e`). No
  `compare.py` invocation and no sim-vs-real arithmetic had been run at that
  commit.
- **Config arguments verified identical to run 3** field by field against the
  `config` block inside each run-3 `sim_*.json`. `perf.json` is the only input
  that differs.
- **The online calibration ran on the same engine state the predictions
  assume**: config A settings, KV pool 87,200 tokens, matching run 3's config A
  exactly.
- **Prefix caching was neutralised in the calibration** by unique per-stream
  prompts; the server reported a 0.0% hit rate for the whole calibration,
  matching the offline fit's `enable_prefix_caching=False`.
- **The mis-specified threshold in (ii) is reported as a defect** (§4.2) rather
  than reinterpreted.
- **No new real runs.** This is stated in the verdict line, in §1, and here,
  because the 10-of-12 figure invites exactly the misreading §1 rules out.

---

## 9. Where this leaves the hypothesis

**What run 4 establishes.** Run 3's §7.1 diagnosis was correct and its fix
works: `a` was fitted on the offline engine while the benchmark measures the
online server, and correcting it closes 83% of the e2e deficit and cuts mean
absolute error across all metrics from 11.6% to 7.0% without disturbing the
cost scorecard. The three-run pattern is now confirmed a third time: **the step
model keeps being adequate; the harness measuring its coefficients keeps being
the defect.**

**What it does not establish.** Nothing about generalisation. This is a
re-prediction against measurements that were already on disk. It also does not
establish that a single per-step constant is the right correction — §6 shows it
is not, and the residuals in §3 and the 16.3% check-point error are what that
costs.

**What is now the open front.** Tail latency, still, and unchanged by this run:
F and G's `ttft_p95` misses are confirmed independent of `a` (§5).

Ranked next steps:

1. **Refit `b_d` and `c_kv` on the online path too, then run a fresh held-out
   config.** §6 shows the offline decode grid could not see the context term at
   all; `perf.json` still carries the flattened values. This is the same fix as
   run 4's, applied to the two coefficients it left frozen — and unlike run 4 it
   must be validated on a config whose measurements do not yet exist. A pool
   size never used (say `gpu-mem-util 0.93`) plus a second axis crossed with it
   would test the whole hybrid at once. **Without this step run 4's result is
   in-sample and stays that way.**
2. **Model queue build-up within a long prefill step** (run 3 §7.2). Now the
   sole surviving explanation for both `ttft_p95` misses, and promoted by §5's
   independence result from "a candidate" to "the candidate".
3. **Change the verdict criterion to report absolute error alongside the
   relative gap, and decide in writing which one carries the verdict.** §7 is
   the case: this run improved almost every absolute error and lost two rows at
   the bar. Run 3 flagged this; run 4 is the demonstration. It belongs between
   rounds, before the next set of predictions is frozen.
4. **Add the TP communication term** — still B's best explanation, still
   un-modelled, and still larger on this box because P2P is unavailable. B's
   throughput error at +5.6% is the largest cost error in the scorecard.
