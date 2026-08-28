# replay-sim v0.6 validation report — run 6

**Date:** 2026-08-28
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Held-out config:** J (gpu-mem-util 0.82, unseen, 5,089 blocks). **Its six rows carry the verdict.**
**Verdict: v1 5 of 6 · v2 5 of 6 — FAIL.**

**Pre-registered predictions: (i) CONFIRMED, (ii) FALSIFIED, (iii) FALSIFIED, (iv) CONFIRMED, (v) SPLIT.**

**Bottom line.** v0.6 does exactly what it claims to the cache: hit rate now responds
to pool size near saturation, and hit-rate error falls from 1.14% to 0.72% mean while
`e2e_p95` error more than halves, 10.77% → **4.29%**. It also **overshoots the TTFT
tail on every config**. Every `ttft_p95` error in the set is now positive; F went from
−31.3% to **+52.9%**, and the held-out miss is J's `ttft_p95` at +32.5%. And the
config the change was designed from — H — **did not move at all**: at 5,811 blocks the
pool still is not pressured even with generated blocks consuming it, so the one row
that motivated v0.6 is the one row v0.6 left untouched.

| Run | Sim | Configs | rows | v1 | v2 | held-out | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| 1 | v0 | A–C | 11 | 1 | 1 | 11 | 1 | 1 |
| 2 | v0.2 | A–E | 23 | 12 | 18 | 12 (D,E) | 9 | 10 |
| 3 | v0.3 | A–G | 35 | 25 | 32 | 12 (F,G) | 10 | 11 |
| 4 | v0.4 | A–G | 35 | 23 | 32 | — | — | — |
| 5 | v0.5 | A–I | 47 | 36 | 44 | 12 (H,I) | 10 | 11 |
| **6** | **v0.6** | **A–J** | **53** | **44** | **50** | **6 (J)** | **5** | **5** |

---

## 1. Install provenance

`perf.json` is **unchanged from run 5** — calibration was out of scope and `git diff`
on it is empty. `simulator.py` is the v0.6 drop-in as delivered, with a single
non-physics edit: `Perf.load`'s tolerance for provenance keys, re-applied because the
archive reverted it and the plain loader raises
`TypeError: Perf.__init__() got an unexpected keyword argument 'a_source'` on the v0.5
`perf.json`. Verified before patching.

**The archive again shipped files that must not be installed.** `calibrate.py` was the
pre-run-4 version (3,516 B against the current 23,319 B carrying the online modes);
copying it would delete runs 4 and 5's calibration work. `workload.py` was the pristine
pre-fix `tok0..tok511` version **for the third consecutive drop-in**. Neither was
copied; the trace was verified unchanged after the swap (`sha256 4e70250f…`).

The archive README also **omits VERDICT CRITERION v2**, which its own Run 6 protocol
depends on ("Criterion v2 … carries the verdict"). It is preserved verbatim in the
installed README rather than dropped, and the substitution is noted there.

---

## 2. The verdict — held-out config J

J at `gpu-mem-util 0.82` probed to 81,424 tokens = **5,089 blocks**, unseen, between
F (4,607) and A (5,450). One fresh real run, `--drop-first 10` on both sides.

| Row | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|
| ttft_p50_s | +0.9% | +0.4% | **0.5 pt** | −6.5% | ✅ | ✅ |
| **ttft_p95_s** | **+27.4%** | **+9.8%** | **17.6 pt** | **+32.5%** | ❌ | ❌ |
| e2e_p50_s | +2.1% | +0.1% | **1.9 pt** | −4.6% | ✅ | ✅ |
| e2e_p95_s | +14.5% | +6.5% | **8.0 pt** | **+2.4%** | ✅ | ✅ |
| throughput_tok_s | −1.2% | −1.8% | **0.6 pt** | −0.5% | ✅ | ✅ |
| prefix_cache_hit_rate | −1.1% | −1.5% | **0.5 pt** | −0.5% | ✅ | ✅ |

**v1 5 of 6 · v2 5 of 6 — FAIL.** Five rows pass by wide margins; `e2e_p95` at +2.4%
absolute is the best e2e tail prediction on any held-out config in the series. The
single miss fails both v2 limbs: gap 17.6 pt *and* absolute error +32.5%.

> **Recorded oddity.** The simulator predicts J (5,089 blocks, mbt 2048) **identically
> to G** (5,106 blocks, mbt 8192) on every metric to three decimals — `ttft_p95` 0.934,
> `e2e_p50` 4.624, hit 0.838. The real engine distinguishes them clearly: real J
> `ttft_p95` 0.705 against real G's 0.829. Two configs differing by a 4× prefill budget
> and 17 blocks are indistinguishable to the model and 18% apart in measurement.

---

## 3. Predictions (i)–(v)

### (i) Sim hit rate responds to pool size near saturation — **CONFIRMED**

| Config | blocks | real | v0.5 sim | err | v0.6 sim | err |
|---|---|---|---|---|---|---|
| C | 2,440 | 0.597 | 0.596 | −0.2% | 0.592 | −0.8% |
| E | 3,644 | 0.726 | 0.738 | +1.7% | 0.723 | **−0.4%** |
| I | 4,298 | 0.797 | 0.808 | +1.4% | 0.789 | −1.0% |
| F | 4,607 | 0.812 | 0.838 | +3.2% | **0.808** | **−0.5%** |
| J | 5,089 | 0.842 | — | — | 0.838 | **−0.5%** |
| G | 5,106 | 0.844 | 0.857 | +1.5% | 0.838 | **−0.7%** |
| **A** | **5,450** | **0.855** | 0.862 | +0.8% | **0.847** | −0.9% |
| D | 5,490 | 0.859 | 0.862 | +0.3% | 0.847 | −1.4% |
| **H** | **5,811** | **0.862** | 0.862 | +0.0% | **0.862** | **+0.0%** |

`sim_A` = 0.847 < `sim_H` = 0.862, breaking v0.5's flat 0.862, and `sim_A` lands inside
the pre-registered [0.840, 0.860]. The values reproduce the changelog's stated
directional check (0.808 / 0.847 / 0.862 at 4,607 / 5,450 / 5,811) **exactly**. Mean
absolute hit-rate error **1.14% → 0.72%**.

As pre-registered, this was a verification rather than a blind prediction: the
changelog states these numbers, so they were readable before the freeze.

### (ii) H `ttft_p95` over-prediction shrinks and H passes v2 — **FALSIFIED**

**H did not move at all.** `sim_H` `ttft_p95` is 0.652 s under both v0.5 and v0.6,
still +20.3% against real 0.542 s, still failing both v2 limbs.

The reason is visible in (i): H's hit rate is 0.862 before and after. At 5,811 blocks
the pool is *still* not under eviction pressure even once generated blocks consume
capacity — the change did not reach far enough up the pool axis to touch the config it
was derived from. v0.6 moved every pool below H and left H exactly where it was.

### (iii) J passes v2 on all six rows — **FALSIFIED**

5 of 6. The miss is `ttft_p95` at +32.5% absolute, 17.6 pt gap — §2.

### (iv) Cost scorecard unchanged, every cost gap ≤ 3 pt — **CONFIRMED**

Worst cost gap **2.8 pt** (B throughput), against v0.5's 2.5 pt. Every hit-rate gap
≤ 1.0 pt. Full table in §5.

**The recorded risk did not fire.** I predicted C's hit rate was the row most likely to
break (iv), since the change can only reduce simulated hit rates and C's was already
near-exact. C moved −0.2% → −0.8% — real but small, and its hit-rate *gap* actually
improved to 0.1 pt. C's pool is small enough that its cache was already thrashing;
adding generated blocks changed little.

### (v) F and G `ttft_p95` absolute errors shrink — **SPLIT: G confirmed, F falsified**

| | real | v0.5 sim | err | v0.6 sim | err | \|err\| change |
|---|---|---|---|---|---|---|
| A | 0.642 | 0.652 | +1.6% | 0.733 | +14.2% | +12.6 pt |
| B | 148.261 | 136.197 | −8.1% | 136.197 | −8.1% | 0.0 pt |
| C | 27.857 | 30.156 | +8.3% | 29.513 | +5.9% | **−2.3 pt** |
| D | 0.583 | 0.652 | +11.8% | 0.733 | +25.7% | +13.9 pt |
| E | 3.190 | 3.556 | +11.5% | 3.572 | +12.0% | +0.5 pt |
| **F** | 1.360 | 0.934 | **−31.3%** | 2.080 | **+52.9%** | **+21.6 pt** |
| **G** | 0.829 | 0.697 | **−15.9%** | 0.934 | **+12.7%** | **−3.3 pt** |
| **H** | 0.542 | 0.652 | +20.3% | 0.652 | +20.3% | 0.0 pt |
| I | 2.634 | 2.356 | −10.6% | 3.054 | +15.9% | +5.4 pt |
| **J**\*\* | 0.705 | — | — | 0.934 | **+32.5%** | — |

**G confirmed**: −15.9% → +12.7%, magnitude down 3.3 points, and it now passes the v2
absolute limb. **F falsified, badly**: −31.3% → **+52.9%**, the largest latency error
in the series, with the sign flipped.

**The pattern across the whole column is the finding.** Every `ttft_p95` error except
B's is now **positive**. v0.6 converted a set of under-predictions into a set of
over-predictions and moved the aggregate the wrong way: mean `ttft_p95` absolute error
**13.26% → 18.65%**. Publishing generated blocks adds eviction pressure, eviction
causes recompute, and recompute lands in the first-token tail — the mechanism is real,
and its magnitude is calibrated too high.

---

## 4. Aggregate movement, A–I

| Metric | v0.5 | v0.6 | change |
|---|---|---|---|
| ttft_p50_s | 7.41% | 7.41% | +0.01 pt |
| **ttft_p95_s** | 13.26% | **18.65%** | **+5.38 pt** |
| e2e_p50_s | 7.65% | **6.71%** | −0.94 pt |
| **e2e_p95_s** | 10.77% | **4.29%** | **−6.48 pt** |
| throughput_tok_s | 1.20% | **1.10%** | −0.11 pt |
| prefix_cache_hit_rate | 1.14% | **0.72%** | −0.42 pt |
| **all metrics** | 7.01% | **6.59%** | **−0.42 pt** |

v0.6 is a **net improvement that trades one metric for another**: `e2e_p95` error more
than halves and `ttft_p95` error grows by 40%. Both moves come from the same mechanism.
The eviction-driven recompute cost lands correctly in end-to-end latency and too
heavily in the first-token tail — consistent with the simulator charging a full prompt
recompute where vLLM recovers part of the prefix.

### In-sample A–I

**v1 39 of 47 · v2 45 of 47.** The two v2 misses are **C `ttft_p50`** (+22.7%, new this
run) and **F `ttft_p95`** (+52.9%). G's `ttft_p95`, a v2 miss in run 5, now passes.

---

## 5. Product scorecard

`**` = held out.

| Config | tput sim/real | err | gap | gpu_s/1k sim / real\* | err | hit sim/real | err | gap |
|---|---|---|---|---|---|---|---|---|
| A | 205.4 / 207.7 | −1.1% | — | 4.667 / 4.514 | +3.4% | 0.847 / 0.855 | −0.9% | — |
| B | 109.1 / 104.6 | +4.3% | **2.8** | 9.148 / 9.411 | −2.8% | 0.000 / n/a | — | — |
| C | 168.9 / 171.2 | −1.3% | **0.2** | 5.796 / 5.542 | +4.6% | 0.592 / 0.597 | −0.8% | **0.1** |
| D | 205.4 / 208.7 | −1.6% | **0.5** | 4.667 / 4.492 | +3.9% | 0.847 / 0.859 | −1.4% | **0.5** |
| E | 200.6 / 199.6 | +0.5% | **1.6** | 4.861 / 4.715 | +3.1% | 0.723 / 0.726 | −0.4% | **0.4** |
| F | 201.3 / 201.3 | **+0.0%** | **1.1** | 4.771 / 4.667 | +2.2% | 0.808 / 0.812 | −0.5% | **0.4** |
| G | 202.9 / 204.4 | −0.7% | **0.4** | 4.728 / 4.596 | +2.9% | 0.838 / 0.844 | −0.7% | **0.2** |
| H | 209.4 / 209.2 | +0.1% | **1.2** | 4.575 / 4.481 | +2.1% | 0.862 / 0.862 | +0.0% | **1.0** |
| I | 201.3 / 200.9 | +0.2% | **1.3** | 4.796 / 4.676 | +2.6% | 0.789 / 0.797 | −1.0% | **0.1** |
| **J**\*\* | 202.9 / 203.9 | **−0.5%** | **0.6** | 4.728 / 4.607 | +2.6% | 0.838 / 0.842 | **−0.5%** | **0.5** |

\* real `gpu_s/1k` is derived from `nvidia-smi`, not measured.

**Cost prediction has now survived six held-out configs across five axes** — pool size
(F, H, J), scheduler (D), prefill granularity (G), and the pool × granularity crossing
(I) — **without a single miss.** J's held-out cost errors are −0.5% throughput and
−0.5% hit rate. Hit-rate gaps are the tightest they have ever been (≤ 1.0 pt), which is
v0.6's clearest win.

---

## 6. Run integrity

- **v0.6 installed and `PREDICTIONS_run6.md` committed before any simulation**
  (`a050e01`), with numeric expectations for (i)–(v), the note that (i) is a
  verification of a changelog-stated check rather than a blind prediction, and the
  recorded risk about C.
- **All ten predictions committed before any real run or comparison** (`2dfd58a`). J
  had no measurement in existence at that commit.
- **`perf.json` byte-identical to run 5**, verified by empty `git diff`.
- **A–I config arguments verified identical** to runs 3/4/5, field by field.
- **J's pool probed from its own startup log before predicting** (81,424 tokens) and
  matched at run time.
- **A–I are in-sample re-predictions** against reals from runs 3 and 5, stated with the
  same prominence run 4 used: they carry no generalisation claim. J alone is held out.
- **The archive's stale `calibrate.py` and pre-fix `workload.py` were not installed**;
  trace provenance verified.

---

## 7. Where this leaves the hypothesis

**What v0.6 got right.** The cache mechanism. Hit rate now tracks pool size across the
whole range instead of saturating, hit-rate error is the lowest in the series, `e2e_p95`
error more than halved, and cost prediction survived a sixth held-out config untouched.
The physics of "generated blocks consume cache capacity" is correct and was worth
adding.

**What it got wrong.** The magnitude, in exactly one place. Every `ttft_p95` in the set
is now over-predicted, mean error up 5.4 points, and the held-out verdict fails on that
single row. The simulator charges a full prompt recompute on eviction; vLLM recovers
whatever prefix survives, so the true tail penalty is smaller than the modelled one.

**What it did not touch.** Config H — the row v0.6 was derived from. At 5,811 blocks the
pool is not pressured even with generated blocks in it, so H's prediction is bit-identical
to v0.5's and still +20.3%. The change explains H's *mechanism* while failing to move
H's *number*.

Ranked next steps:

1. **Make eviction recompute partial, not total.** One change, and it is the direct
   cause of the `ttft_p95` overshoot: a preempted or evicted request should re-match
   whatever prefix blocks survived rather than recomputing the whole prompt. This should
   pull every positive `ttft_p95` error down while leaving `e2e_p95` and the cost
   scorecard — v0.6's wins — where they are.
2. **Give the model a reason to distinguish J from G.** §2: the simulator returns
   identical predictions for a 4× difference in prefill budget at nearly the same pool,
   and the engine reports an 18% difference. Whatever separates them is not represented
   at all.
3. **Re-test H with item 1 applied.** H is the only held-out row in the series that has
   never moved. If partial recompute does not move it either, H needs its own hypothesis
   rather than inheriting one.
4. **TP communication term** — B's throughput error is +4.3% and its cost gap 2.8 pt,
   the largest remaining in the scorecard, and still the only config with no modelled
   communication cost.
