# replay-sim v0.7 validation report — run 7

**Date:** 2026-08-28
**Criterion:** v2 carries the verdict; both counts reported for series continuity.
**Held-out config:** K (gpu-mem-util 0.75, unseen, 4,246 blocks — the pressure zone).
**Verdict: v1 5 of 6 · v2 5 of 6 — FAIL.**

**Predictions: (i) FALSIFIED · (ii) SPLIT · (iii) CONFIRMED · (iv) FALSIFIED.**

**Bottom line.** v0.7's leaf-first eviction order was aimed at run 6's uniform
`ttft_p95` over-prediction. It **did not hit it**. Three of nine positive errors moved;
six did not budge at all, including **F — predicted to move the most — which moved
exactly zero** (+52.9% under both v0.6 and v0.7). The held-out verdict fails on the
same row as run 6, `ttft_p95`, at +37.0%.

What the change did do is finish the cache. Prefix-cache hit-rate error is now
**0.19% mean** and exact on six of eleven configs; the worst cost gap in the whole
scorecard is **2.0 pt**. And prediction (iii) — the one that predicted *no* movement —
is the only one that held, exactly.

**The load-bearing result is negative and it is now well tested.** Across v0.5, v0.6
and v0.7 the failing tail rows are F +52.9% (three versions, two values), J +32.5%
(unchanged), H **+20.3% under all three**, and K +37.0%. Two consecutive cache changes
in opposite directions — one adding eviction pressure, one reordering it — left them
where they were. **The residual `ttft_p95` error is not a prefix-cache phenomenon.**

| Run | Sim | Configs | rows | v1 | v2 | held-out | v1 | v2 |
|---|---|---|---|---|---|---|---|---|
| 1 | v0 | A–C | 11 | 1 | 1 | 11 | 1 | 1 |
| 2 | v0.2 | A–E | 23 | 12 | 18 | 12 (D,E) | 9 | 10 |
| 3 | v0.3 | A–G | 35 | 25 | 32 | 12 (F,G) | 10 | 11 |
| 4 | v0.4 | A–G | 35 | 23 | 32 | — | — | — |
| 5 | v0.5 | A–I | 47 | 36 | 44 | 12 (H,I) | 10 | 11 |
| 6 | v0.6 | A–J | 53 | 44 | 50 | 6 (J) | 5 | 5 |
| **7** | **v0.7** | **A–K** | **59** | **48** | **56** | **6 (K)** | **5** | **5** |

---

## 1. Install provenance

`perf.json` is **byte-identical to runs 5 and 6** (`git diff` empty). Only
`simulator.py` and the two named README sections were taken from the archive. The
delivered change is one line — `for h in reversed(r.pinned)` at `simulator.py:185` —
confirmed to be the only physics difference from v0.6.

One non-physics edit: `Perf.load`'s provenance-key tolerance, re-applied because the
archive reverted it again. Without it the loader raises
`TypeError: unexpected keyword argument 'a_source'` on `perf.json`; verified before
patching.

**Fourth consecutive drop-in shipping files that must not be installed**: a pre-run-4
`calibrate.py` (3,516 B against the installed 23,319 B carrying the online calibration
modes) and the pristine pre-fix `workload.py`. Neither copied. Trace verified unchanged
after the swap: `sha256 4e70250f…`. The archive README again omitted VERDICT CRITERION
v2 and all run 4–6 material; only the two named sections were appended.

---

## 2. The verdict — held-out config K

K at `gpu-mem-util 0.75` probed to 67,936 tokens = **4,246 blocks**, unseen, between
E (3,644) and F (4,607). One fresh real run, `--drop-first 10` on both sides.

| Row | sim Δ | real Δ | gap | abs err | v1 | v2 |
|---|---|---|---|---|---|---|
| ttft_p50_s | +6.6% | +6.9% | **0.4 pt** | −7.2% | ✅ | ✅ |
| **ttft_p95_s** | **+269.9%** | **+193.6%** | 76.3 pt | **+37.0%** | ❌ | ❌ |
| e2e_p50_s | +7.0% | +8.2% | **1.2 pt** | −7.5% | ✅ | ✅ |
| e2e_p95_s | +45.1% | +35.5% | **9.6 pt** | **−3.4%** | ✅ | ✅ |
| throughput_tok_s | −3.4% | −3.3% | **0.1 pt** | **+0.2%** | ✅ | ✅ |
| prefix_cache_hit_rate | −7.5% | −7.4% | **0.1 pt** | **+0.0%** | ✅ | ✅ |

**v1 5 of 6 · v2 5 of 6 — FAIL.** The five passing rows are the best held-out set in
the series: `e2e_p95` at −3.4% absolute, throughput at +0.2%, and hit rate **exact to
three decimals** with a 0.1 pt gap. K's real hit rate fell to 0.792 from A's 0.855 and
the simulator predicted 0.792.

The one miss fails both v2 limbs: gap 76.3 pt **and** absolute error +37.0%. Same row
as run 6's J miss, same sign, larger.

---

## 3. Predictions (i)–(iv)

### (i) Every positive `ttft_p95` error decreases; F moves most; J passes v2 — **FALSIFIED**

| Config | real | v0.5 | v0.6 | **v0.7** | v0.6→v0.7 |
|---|---|---|---|---|---|
| A | 0.642 | +1.6% | +14.2% | **+8.7%** | **−5.5 pt** |
| B | 148.261 | −8.1% | −8.1% | −8.1% | 0.0 pt |
| C | 27.857 | +8.3% | +5.9% | +8.1% | +2.2 pt |
| D | 0.583 | +11.8% | +25.7% | **+11.8%** | **−13.9 pt** |
| E | 3.190 | +11.5% | +12.0% | +12.3% | +0.3 pt |
| **F** | 1.360 | −31.3% | **+52.9%** | **+52.9%** | **0.0 pt** |
| G | 0.829 | −15.9% | +12.7% | +12.7% | 0.0 pt |
| **H** | 0.542 | +20.3% | +20.3% | **+20.3%** | **0.0 pt** |
| I | 2.634 | −10.6% | +15.9% | **+12.3%** | **−3.7 pt** |
| **J** | 0.705 | — | +32.5% | **+32.5%** | **0.0 pt** |
| **K**\*\* | 1.885 | — | — | **+37.0%** | — |

Nine positive errors under v0.6. **Three decreased** (A, D, I). Six did not: C got
worse by 2.2 pt, E by 0.3, and F, G, H, J are **bit-identical**.

- **"F moves the most" — falsified outright.** F moved zero. D moved the most, 13.9 pt.
- **"J passes v2" — falsified.** J is unchanged at +32.5% and still fails.

The change works where it fires and does not fire where it is needed. G and J's hit
rates *did* improve (0.838 → 0.843 and 0.842) while their `ttft_p95` stayed identical
to three decimals — the reordering reaches the cache without reaching the tail.

### (ii) `e2e_p95` and cost within noise; pressure-zone hit rates rise — **SPLIT**

**Cost clause — holds, emphatically.** Worst cost gap **2.0 pt** against a ≤3 pt
threshold, the best in the series (v0.6: 2.8 pt). Full table in §5.

**Hit-rate clause — 3 of 4.** E −0.4% → −0.3%, F −0.5% → −0.4%, I −1.0% → **+0.0%**.
C stayed flat at −0.8%; at 2,440 blocks its cache thrashes regardless of ordering.

**`e2e_p95` clause — breached.** Mean absolute error **4.11% → 6.54%**, over the ≤6%
I pre-registered. v0.6's single best result is partly given back: G +4.0% → −6.1%,
J +2.4% → −7.5%, D −0.6% → −9.2%, A −4.7% → −9.8%. Reordering eviction returns
capacity to running sequences, which shortens simulated end-to-end times below the
measured ones.

### (iii) H does **not** move materially — **CONFIRMED, exactly**

H's `ttft_p95` absolute error is **+20.3% under v0.5, v0.6 and v0.7** — bit-identical
across three simulator versions and two cache changes in opposite directions. Inside
the pre-registered [+17.3%, +23.3%], and the H row still fails v2.

**This is the run's most useful result.** Run 6 §7 argued H's miss is a different
mechanism — real tail relief from surplus pool with *no* eviction pressure — that no
eviction change can reach. (iii) turned that from an inherited excuse into a
prediction, and the prediction held under a direct test. At 5,811 blocks there is
nothing to evict, so there is nothing for an eviction-order change to reorder. **H now
needs its own hypothesis; it can no longer inherit each run's cache change.**

### (iv) K passes v2 on all six rows — **FALSIFIED**

5 of 6, missing `ttft_p95` at +37.0% — §2. Run 6 predicted the same for J and got the
same 5 of 6, missing the same row. Two held-out configs, two runs, one row.

> **Recorded: (i) and (iii) were in direct tension and I said so before running.** (i)
> required every positive error including H's to decrease; (iii) required H not to
> move. I pre-registered that both would be scored as written and that my expectation
> was H staying put. H stayed put: (iii) confirmed, (i) falsified on that row and on
> five others besides.

---

## 4. Aggregate movement, A–J

| Metric | v0.6 | v0.7 | change |
|---|---|---|---|
| ttft_p50_s | 7.32% | **5.35%** | −1.97 pt |
| ttft_p95_s | 20.03% | **17.98%** | −2.05 pt |
| e2e_p50_s | 6.51% | **6.22%** | −0.28 pt |
| e2e_p95_s | 4.11% | 6.54% | **+2.44 pt** |
| throughput_tok_s | 1.04% | **0.81%** | −0.23 pt |
| prefix_cache_hit_rate | 0.70% | **0.19%** | −0.51 pt |
| **all metrics** | 6.72% | **6.28%** | **−0.43 pt** |

A small net improvement that again trades one metric for another, mirroring run 6:
v0.6 halved `e2e_p95` error and inflated `ttft_p95`; v0.7 recovers some `ttft_p95` and
gives back `e2e_p95`. Neither reaches the rows that actually fail.

**In-sample A–J: v1 43 of 53 · v2 51 of 53.** The two v2 misses are **F `ttft_p95`**
(+52.9%) and **J `ttft_p95`** (+32.5%) — unchanged from run 6. C's `ttft_p50`, a v2
miss in run 6 at +22.7%, now passes.

---

## 5. Product scorecard

`**` = held out.

| Config | tput sim/real | err | gap | gpu_s/1k sim / real\* | err | hit sim/real | err | gap |
|---|---|---|---|---|---|---|---|---|
| A | 208.3 / 207.7 | +0.3% | — | 4.601 / 4.514 | +1.9% | 0.856 / 0.855 | **+0.1%** | — |
| B | 109.1 / 104.6 | +4.3% | **2.0** | 9.148 / 9.411 | −2.8% | 0.000 / n/a | — | — |
| C | 167.6 / 171.2 | −2.1% | **2.0** | 5.844 / 5.542 | +5.5% | 0.592 / 0.597 | −0.8% | **0.7** |
| D | 209.0 / 208.7 | +0.1% | **0.1** | 4.584 / 4.492 | +2.0% | 0.859 / 0.859 | **+0.0%** | **0.1** |
| E | 200.6 / 199.6 | +0.5% | **0.2** | 4.861 / 4.715 | +3.1% | 0.724 / 0.726 | −0.3% | **0.3** |
| F | 201.7 / 201.3 | +0.2% | **0.1** | 4.762 / 4.667 | +2.0% | 0.809 / 0.812 | −0.4% | **0.5** |
| G | 204.5 / 204.4 | **+0.0%** | **0.2** | 4.690 / 4.596 | +2.0% | 0.843 / 0.844 | −0.1% | **0.2** |
| H | 209.4 / 209.2 | +0.1% | **0.2** | 4.575 / 4.481 | +2.1% | 0.862 / 0.862 | **+0.0%** | **0.1** |
| I | 201.3 / 200.9 | +0.2% | **0.1** | 4.780 / 4.676 | +2.2% | 0.797 / 0.797 | **+0.0%** | **0.1** |
| J | 204.3 / 203.9 | +0.2% | **0.1** | 4.694 / 4.607 | +1.9% | 0.842 / 0.842 | **+0.0%** | **0.1** |
| **K**\*\* | 201.3 / 200.9 | **+0.2%** | **0.1** | 4.788 / 4.676 | +2.4% | 0.792 / 0.792 | **+0.0%** | **0.1** |

\* real `gpu_s/1k` is derived from `nvidia-smi`, not measured.

**The cost model is finished.** Hit rate is exact to three decimals on six of eleven
configs and within 0.8% on the rest; every hit-rate gap ≤ 0.7 pt; throughput within
0.5% on nine of eleven. **Seven held-out configs across five axes — pool size (F, H, J,
K), scheduler (D), prefill granularity (G), and the pool × granularity crossing (I) —
with no cost miss in the series.**

---

## 6. Run integrity

- **v0.7 installed and `PREDICTIONS_run7.md` committed before any simulation**
  (`029ed86`), with numeric expectations for (i)–(iv) and the recorded tension between
  (i) and (iii) on config H, including which way I expected it to resolve.
- **All eleven predictions committed before any real run or comparison** (`2714147`).
  K had no measurement in existence at that commit.
- **`perf.json` byte-identical to runs 5 and 6**, verified by empty `git diff`.
- **A–G config arguments verified identical** to runs 3–6, field by field.
- **K's pool probed from its own startup log before predicting** (67,936 tokens).
- **A–J are in-sample re-predictions** against reals from runs 3, 5 and 6.
- **The archive's stale `calibrate.py` and pre-fix `workload.py` were not installed**;
  trace provenance verified by sha256.

---

## 7. Where this leaves the hypothesis

**What is finished.** Cost. Seven held-out configs, five axes, no miss, and hit-rate
prediction now exact on more than half the set. Whatever else is open, "what will this
config change do to my serving cost and cache efficiency" is answered.

**What two runs have now ruled out.** The tail is not a prefix-cache problem. v0.6
added eviction pressure and pushed every `ttft_p95` up; v0.7 reordered eviction and
pulled three back down while leaving F, G, H and J bit-identical. The rows that fail
are insensitive to both. F has been at +52.9% across two versions, J at +32.5%, and
H at **+20.3% across three**.

**What (iii) established.** H's miss is a distinct mechanism, confirmed by a prediction
that it would not move. It cannot be addressed by cache work at all — at 5,811 blocks
there is nothing to evict.

Ranked next steps:

1. **Stop changing the cache to fix the tail.** Two opposed cache changes have now
   failed to move the failing rows. The next change should be aimed at `ttft_p95`
   directly, with a measurement first: instrument which requests occupy the p95 in
   both sim and real for F, J and K, and compare their *individual* waits rather than
   the percentile. The percentile has been the unit of analysis for four runs and it
   has hidden which requests are wrong.
2. **Give H its own hypothesis.** (iii) confirmed it is not a cache effect. Real H is
   *faster* than real A at the tail with 6.6% more pool and no eviction pressure in
   either — an effect the model has no term for. Candidates: allocator fragmentation,
   or CUDA-graph capture differences at different pool sizes.
3. **Distinguish J from G.** Still unaddressed from run 6: the simulator returns
   identical predictions for a 4× prefill-budget difference at nearly the same pool,
   and the engine reports `ttft_p95` 0.705 vs 0.829.
4. **TP communication term** — B's throughput error is +4.3% and its cost gap 2.0 pt,
   now the largest remaining item in an otherwise finished scorecard.
