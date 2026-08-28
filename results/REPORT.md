# replay-sim v0.5 validation report — run 5

**Date:** 2026-08-28
**Criterion:** **v2** (adopted in README between runs 4 and 5). Both counts reported.
**Held-out configs:** H (pool 0.88, unseen and above every prior point), I (0.78 × mbt 8192, crossed axes).
**Verdict on held-out H+I:** **v1 10 of 12 · v2 11 of 12 — FAIL under both.**
**Pre-registered predictions:** (i) **met**, (ii) **CONFIRMED**, (iii) **FALSIFIED — and exactly inverted.**

**Bottom line.** Completing the online calibration did what it was supposed to do
*to the calibration*: the held-out check point went from −16.5% to **−3.2%**, decode
fit R² from 0.951 to **0.996**, and `c_kv` came out **8× larger** than the offline
harness could see. It did **not** improve aggregate accuracy on A–G — mean absolute
error is 7.2% against v0.4's 7.0%. What it bought instead is a model whose
coefficients are all measured on the right path, and that generalised to two new
held-out axes at 11 of 12 rows under v2.

The interesting result is prediction (iii). I predicted H would pass and I would
miss, on the theory that queue build-up behind long prefill steps is the remaining
mechanism. **The opposite happened.** I — the config crossing both mechanisms that
caused every previous tail miss — is predicted to within **10.6%**. H, the quiet
large-pool config, is the only miss, and it is the first **over**-prediction in the
series: the simulator says a bigger pool changes nothing, and the real engine's tail
got 15.6% faster.

---

## 1. Criterion v2, and the whole series under both counts

v2 is adopted verbatim in `README.md`. `replay_sim/verdict.py` implements both
criteria in one code path; its v1 counts reproduce every published figure exactly.

| Run | Sim | Configs | rows | v1 | v2 | held-out rows | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| 1 | v0 | A–C | 11 | 1 | 1 | 11 | **1** | **1** |
| 2 | v0.2 | A–E | 23 | 12 | 18 | 12 (D,E) | **9** | **10** |
| 3 | v0.3 | A–G | 35 | 25 | 32 | 12 (F,G) | **10** | **11** |
| 4 | v0.4 | A–G | 35 | 23 | 32 | — | — | — |
| **5** | **v0.5** | **A–I** | **47** | **36** | **44** | **12 (H,I)** | **10** | **11** |

Each run is scored against its own real measurements; runs 4 and 5 reuse run 3's
reals for A–G by design.

Two things the v2 column shows that v1 hid. Run 3 → run 4 reads as a regression
under v1 (25 → 23) and as **flat** under v2 (32 → 32) — the run-4 report argued
this from absolute error; v2 now scores it. And v0's failure in run 1 was real by
both measures (1 of 11 either way): v2 is not a softer bar, it is a differently
shaped one. Under v2 a latency row passes only if the *absolute* prediction is
good, which is why B's thousand-point gaps pass while H's 15.6-pt gap does not.

---

## 2. The calibration is now entirely on the online path

`b_d` and `c_kv` now come from the same steady-state-window method run 4 used for
`a`, sweeping batch **and** context over 14 points; `b_p` comes from the TTFT of a
single unloaded request through the same client. Every coefficient is measured on
the path `bench.py` exercises.

| | a (ms) | b_p | b_d | c_kv | decode R² |
|---|---|---|---|---|---|
| v0.3 offline | 12.935 | 0.00041897 | 0.00032273 | 0.01607 | 0.95147 |
| v0.4 hybrid | 16.111 | 0.00041897 | 0.00032273 | 0.01607 | — |
| **v0.5 online** | **12.665** | **0.00040749** | **0.00041372** | **0.12793** | **0.99618** |

**`c_kv` is 8.0× the offline value, and `a` falls back to roughly where the offline
fit had it.** Run 4's inflated `a` was standing in for a context term the offline
harness could not see — run 4 §6 predicted exactly this and it is now measured.
`b_d` is 28% larger; `b_p` moves −2.7% (prefill fit R² 0.99988), so the prefill
coefficient was the one thing the offline harness had right.

Decode residuals are within ±2.2 ms at every one of the 14 points, worst relative
residual +6.2%.

### Prediction (i) — the calibration's own held-out test

`B=16 / ctx=3072`, excluded from every fit, measured at 26.42 ms:

| model | predicted | error |
|---|---|---|
| v0.3 | 18.89 ms | −28.5% |
| v0.4 | 22.06 ms | −16.5% |
| **v0.5** | **25.57 ms** | **−3.2%** |

Threshold (<5%) met. **Recorded plainly: this was computed inside `calibrate.py`
and was known before `PREDICTIONS_run5.md` was written**, because the check point is
a calibration output. It is the calibration's held-out test, not a blind prediction
of a later step. (ii) and (iii) are the genuine pre-registrations.

---

## 3. H as specified is not runnable on this box

H was specified at `gpu-mem-util 0.93`. It does not come up. The ladder, run before
any prediction:

| util | result |
|---|---|
| 0.93 | SERVER_DIED after 35 s — CUDA OOM in CUDA-graph capture |
| 0.90 | SERVER_DIED after 40 s — CUDA OOM |
| **0.88** | **READY after 35 s — highest bootable point** |
| 0.86 | READY after 35 s |

At 0.93 the engine sizes the pool (`GPU KV cache size: 102,608 tokens`) and then
dies capturing CUDA graphs, with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
already set. Same failure mode `serve.sh` documents at 0.90 since run 2.

**H was run at 0.88**, which is still an unseen pool point and still above every
utilisation used in runs 1–4 (max 0.85), so the extrapolation H exists to test is
preserved. Decided and written down before any prediction was generated.

> **Method error, recorded.** My first version of `scripts/probe_pool.sh` did not
> forward the utilisation override to `serve.sh`, so an earlier ladder that read
> "0.90/0.88/0.87/0.86/0.82 all fail" had in fact run every probe at 0.93. I found
> it because 0.82 failing while 0.85 works is impossible. The script was fixed and
> the ladder above is the corrected one. **The bad ladder never reached a
> prediction.** Full trace in `results/logs/pool_ceiling_run5.txt`.

**This is also a product finding.** "Can I run at 0.93?" is exactly the question
this simulator exists to answer, and the answer here is "the server will not
start" — a failure mode the simulator has no representation of at all. It predicts
a pool it cannot know is unreachable.

### Probed pools, before predicting

| | spec | probed pool | blocks |
|---|---|---|---|
| H | 0.88, mns 128, mbt 2048 | 92,976 tok | 5,811 |
| I | 0.78, mns 128, mbt 8192 | 68,768 tok | 4,298 |

I's pool is **smaller than F's 73,712 at the same 0.78**: the 8192-token prefill
budget costs activation memory that would otherwise be KV. The crossed axes
interact before a single request is served — something neither axis showed alone.

---

## 4. Held-out results — H and I

Deltas are against run 3's `real_A.json`, the baseline every prior run used, as
fixed in the prediction freeze.

### H vs A (pool 0.88, unseen) — v1 5/6, v2 5/6

| Row | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|
| ttft_p50_s | +0.0% | +0.0% | **0.0 pt** | −7.7% | ✅ | ✅ |
| **ttft_p95_s** | **+0.0%** | **−15.6%** | **15.6 pt** | **+20.3%** | ❌ | ❌ |
| e2e_p50_s | +0.0% | −1.8% | **1.8 pt** | −5.5% | ✅ | ✅ |
| e2e_p95_s | +0.0% | −4.4% | **4.4 pt** | −9.0% | ✅ | ✅ |
| throughput_tok_s | +0.0% | +0.7% | **0.7 pt** | +0.1% | ✅ | ✅ |
| prefix_cache_hit_rate | +0.0% | +0.8% | **0.8 pt** | +0.0% | ✅ | ✅ |

### I vs A (0.78 × mbt 8192, crossed) — v1 5/6, **v2 6/6**

| Row | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|
| ttft_p50_s | +7.5% | +4.1% | **3.4 pt** | −4.7% | ✅ | ✅ |
| **ttft_p95_s** | **+261.3%** | **+310.3%** | 48.9 pt | **−10.6%** | ❌ | ✅ |
| e2e_p50_s | +4.5% | +5.1% | **0.6 pt** | −7.7% | ✅ | ✅ |
| e2e_p95_s | +40.4% | +34.3% | **6.2 pt** | −9.0% | ✅ | ✅ |
| throughput_tok_s | −3.9% | −3.3% | **0.6 pt** | +0.2% | ✅ | ✅ |
| prefix_cache_hit_rate | −6.3% | −6.8% | **0.5 pt** | +1.4% | ✅ | ✅ |

**Held-out total: v1 10 of 12, v2 11 of 12.**

---

## 5. Prediction (iii) — falsified, and inverted

> **Predicted: H `ttft_p95` PASSES under v2. I `ttft_p95` FAILS under v2.**
> Reasoning frozen in `PREDICTIONS_run5.md`: I crosses the two mechanisms behind
> every tail miss in runs 3–4 (long prefill steps, tight pool), and nothing in run 5
> addresses queueing; H is a quiet large-pool config like A/D/G.

**Result: H fails. I passes. Both calls wrong, in both directions.**

**I is the strong result.** The config built to combine G's 8192-token prefill steps
with F's pool pressure produces a 4.8× real tail increase (0.642 → 2.634 s), and
v0.5 predicts 2.356 s — **−10.6% absolute**. Its v1 gap of 48.9 pt is the
small-baseline amplification again: dividing by A's 0.642 s turns a 0.28 s error
into 49 points. **The queue-build-up mechanism I have been carrying since run 3
§7.2 as "the remaining defect" did not produce a miss when tested directly on the
config designed to trigger it.** That hypothesis is now much weaker than run 4 §5
left it.

**H is the new finding, and it is a different failure.** It is the **first
over-prediction** in the series: sim 0.652 s against real 0.542 s, +20.3%. The
simulator predicts H *identically to A* on every metric — because at 5,450 and
5,811 blocks the pool binds in neither case, so nothing in the model changes. The
real engine's tail got **15.6% faster** with 6.6% more pool.

The mechanism is visible in the cache column. Real hit rate moves 0.855 → 0.862
from A to H; the simulator predicts 0.862 for both. **The simulator's prefix cache
has already saturated at 0.862 by 5,450 blocks**, so it has no way to express the
tail relief that extra pool actually buys — fewer late-arriving requests losing
cached blocks to eviction. The model is right that the pool is not binding for
*admission*; it is wrong that the pool stops mattering.

---

## 6. Prediction (ii) — confirmed, with the recorded risk firing the other way

> The high-batch group improves by more points than the low-batch group.

| group | configs | v0.4 mean \|e2e err\| | v0.5 | improvement |
|---|---|---|---|---|
| high-batch / queue-bound | B, C | 9.74% | **7.06%** | **+2.68 pt** |
| low-batch | A, D, F, G | 9.07% | 10.64% | **−1.57 pt** |

**CONFIRMED** (+2.68 > −1.57). C's `e2e_p50` carries it: −16.0% → −7.2%. The 8×
`c_kv` adds time in proportion to batch × context, which is exactly where the
high-batch configs live.

**The recorded risk fired, but in the opposite direction to the one I named.** I
predicted the low-batch group might get worse by *overshooting into positive
error*. It got worse by **under-predicting more** — A `e2e_p50` −3.3% → −7.2%, D
−2.3% → −6.2%, G −2.8% → −6.7%. With `a` falling back from 16.111 to 12.665 ms,
the low-batch configs lost more from the smaller constant than they regained from
the larger context term. 13 of 14 e2e rows remain under-predictions. The outcome
matched the risk; the mechanism I gave for it did not.

Aggregate on A–G is a wash:

| Metric | v0.3 | v0.4 | v0.5 |
|---|---|---|---|
| ttft_p50_s | 7.7% | **5.0%** | 7.7% |
| ttft_p95_s | 12.1% | 14.9% | **12.6%** |
| e2e_p50_s | 23.1% | **7.2%** | 8.0% |
| e2e_p95_s | 22.1% | **11.3%** | **11.3%** |
| throughput_tok_s | 1.9% | **1.4%** | 1.5% |
| prefix_cache_hit_rate | 1.5% | **1.3%** | **1.3%** |
| **all metrics** | 11.6% | **7.0%** | 7.2% |

**Run 5 did not improve aggregate accuracy on the in-sample configs.** It improved
the calibration's own held-out point by a factor of five, moved every coefficient
onto the measured path, and held generalisation on two new axes. That is the honest
summary: this run bought correctness of construction, not a better number.

---

## 7. In-sample A–G (development data, proves nothing)

**v1 26 of 35 · v2 33 of 35.** Seven rows pass under v2 but not v1 — four B rows,
two C rows and E `ttft_p95` — with gaps from 17 to 2,204 points against absolute
errors of 6.4% to 11.5%. That is the small-baseline amplification, priced correctly.

**The two rows that fail under both are F `ttft_p95` (−31.3% absolute) and G
`ttft_p95` (−15.9%)** — the same two rows that were held out and missed in run 3,
still missing under v0.5. This matters for §5. Config I, built to combine F's and
G's mechanisms, passes v2 at −10.6%, while F and G individually still fail. So the
tail defect is **not** the crossing of pool pressure and prefill granularity, and it
is not fixed by better coefficients. G is a new v2 casualty: it passed v2 under v0.4
at −9.9% and fails under v0.5 at −15.9%, just over the line.

---

## 8. Product scorecard

`**` = held out.

| Config | tput sim/real | err | gap | gpu_s/1k sim / real\* | err | hit sim/real | err | gap |
|---|---|---|---|---|---|---|---|---|
| A | 209.4 / 207.7 | +0.8% | — | 4.575 / 4.514 | +1.4% | 0.862 / 0.855 | +0.8% | — |
| B | 109.1 / 104.6 | +4.3% | **1.7** | 9.148 / 9.411 | −2.8% | 0.000 / n/a | — | — |
| C | 167.4 / 171.2 | −2.2% | **2.5** | 5.851 / 5.542 | +5.6% | 0.596 / 0.597 | −0.2% | **0.7** |
| D | 209.4 / 208.7 | +0.3% | **0.5** | 4.575 / 4.492 | +1.8% | 0.862 / 0.859 | +0.3% | **0.5** |
| E | 200.6 / 199.6 | +0.5% | **0.3** | 4.861 / 4.715 | +3.1% | 0.738 / 0.726 | +1.7% | **0.7** |
| F | 202.9 / 201.3 | +0.8% | **0.0** | 4.728 / 4.667 | +1.3% | 0.838 / 0.812 | +3.2% | **2.2** |
| G | 207.6 / 204.4 | +1.6% | **0.7** | 4.616 / 4.596 | +0.4% | 0.857 / 0.844 | +1.5% | **0.7** |
| **H**\*\* | 209.4 / 209.2 | **+0.1%** | **0.7** | 4.575 / 4.481 | +2.1% | 0.862 / 0.862 | **+0.0%** | **0.8** |
| **I**\*\* | 201.3 / 200.9 | **+0.2%** | **0.6** | 4.771 / 4.676 | +2.0% | 0.808 / 0.797 | +1.4% | **0.5** |

\* real `gpu_s/1k` is derived from `nvidia-smi`, not measured.

**Cost prediction generalised again, and on the held-out configs it is the best it
has ever been**: H throughput error +0.1%, I +0.2%, both hit-rate gaps under 1
point, every cost gap in the table ≤ 2.5 pt against a 15-point bar. Three runs of
held-out configs across five axes — pool size (F, H), scheduler (D), prefill
granularity (G), and now the pool × granularity crossing (I) — have not produced a
cost miss.

---

## 9. Run integrity

- **Drift control.** Config A was re-run for real in run 5, pre-registered as a
  control that enters no delta or verdict. Against run 3: `ttft_p50` +0.0%,
  `ttft_p95` +0.2%, `e2e_p50` +0.0%, `e2e_p95` +0.4%, throughput and makespan
  identical to the reported digit. **The box has not drifted**, so reusing run 3's
  A–G measurements is sound.
- **Calibration and predictions committed before any simulation** (`0ef1599`),
  including the H substitution and the probe-script error.
- **All nine predictions committed before any real run or comparison** (`ece387b`).
  H and I had no measurements in existence at that commit.
- **Held-out runs executed first** (H, then I), before the A drift control.
- **A–G config arguments verified identical** to runs 3 and 4, field by field.
- **Pool figures probed from each config's own startup log before predicting**;
  H's run pool (92,976) and I's (68,768) both matched their probes exactly — the
  non-deterministic sizing seen in runs 1–3 did not recur.
- **Prediction (iii) is reported as falsified**, with the inverted result stated
  before any reinterpretation of the mechanism.

---

## 10. Where this leaves the hypothesis

**What five runs have established.** Cost prediction is solved for this workload
and generalises: five held-out axes, no cost miss, held-out throughput error now
±0.2%. The calibration harness — the actual defect in runs 2, 3 and 4 — is fixed:
every coefficient is measured on the path the benchmark uses, the decode fit is
R² 0.996, and its held-out check point is −3.2%.

**What run 5 changes about the diagnosis.** The queue-build-up story is much weaker.
Config I was built to trigger it and v0.5 predicts I's tail to −10.6%. Meanwhile
the one held-out miss is a config where nothing was supposed to happen, and it is
an over-prediction driven by a **saturated prefix-cache model** rather than by
queueing at all.

**What is still not established.** Tail latency under v2 is now a single row out of
twelve held-out, but that row is a new mechanism, not a residue of the old one.

Ranked next steps:

1. **Fix the cache saturation H exposed.** The simulator returns hit rate 0.862 and
   an identical tail for 5,450 and 5,811 blocks; the real engine improves both. The
   cache model stops responding to pool size well before the real one does. This is
   the only held-out v2 miss in run 5 and the first over-prediction in the series.
2. **The queue-build-up hypothesis is now contradicted by its own test.** I combines
   both of its mechanisms and passes v2 at −10.6%, while F (−31.3%) and G (−15.9%)
   still fail under v0.5 — measured this run, §7. A hypothesis whose combined case
   passes while both single cases fail is the wrong hypothesis. What F, G and H have
   in common and I does not is worth the next held-out design: all three sit at or
   near a pool where the cache is saturated in the model but not in the engine, which
   is the same defect as item 1.
3. **Model the startup ceiling.** The simulator will happily predict a config the
   server cannot boot. A calibrated maximum utilisation, recorded per box, would
   turn "0.93 gives you N blocks" into "0.93 does not start here".
4. **TP communication term** — B's throughput error is +4.3%, the largest in the
   scorecard, and still the only config with no modelled communication cost.
