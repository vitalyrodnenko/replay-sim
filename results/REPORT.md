# replay-sim run 8a — diagnostic report

**Date:** 2026-08-28
**No physics change. No predictions. No verdict.** Measurement only.
**Simulator:** v0.7 as installed in run 7, plus `--per-request`. `perf.json` unchanged since run 5.

**What this run answers.** For the four configs whose `ttft_p95` has resisted every
change (F, J, K and H), it identifies *which requests* occupy the tail in sim and in
real, and whether they are the same ones.

**All four verdicts agree: SAME requests — a magnitude problem, not a mechanism
problem.** Overlap of the top-5% `ttft` sets: **K 9/9, F 7/9, J 7/9, H 6/9.**

**And the magnitude is localised to one cohort.** In every config the entire residual
sits on requests where the simulator's prefix match collapses to exactly **1,200 tokens**
— the shared system prompt, the point at which sessions diverge. Everything else is
right to within 14 ms:

| Config | blocks | capped at 1,200 | mean `ttft` error, capped | mean `ttft` error, all others |
|---|---|---|---|---|
| H | 5,811 | **14** of 182 | **+0.166 s** | +0.006 s |
| J | 5,089 | **18** of 182 | **+0.268 s** | +0.008 s |
| F | 4,607 | **25** of 182 | **+0.391 s** | +0.014 s |
| K | 4,246 | **28** of 182 | **+0.316 s** | +0.004 s |

---

## 1. Install and integrity

Taken from the archive: `simulator.py`, `bench.py`, the new `replay_sim/diagnose.py`,
and the "Diagnostic run 8a" README section. **Verified: the installed `simulator.py`
differs from the run-7 committed version only by the `--per-request` dump code** (plus
`Perf.load`'s provenance tolerance, which the archive reverted for the third time and
which was re-applied). No physics difference; `perf.json` diff is empty.

**Fifth consecutive drop-in shipping the pre-run-4 `calibrate.py` and the pristine
pre-fix `workload.py`.** Neither installed. Trace verified unchanged: `sha256 4e70250f…`.

Re-simulation of F, J, K, H used config arguments verified identical to run 7 field by
field, and **reproduced run 7's summary metrics exactly** on all six metrics for all
four configs. The diagnostic benches wrote to `results/diag/`; the series' canonical
`real_<cfg>.json` were never touched.

### Diagnostic re-run vs canonical real — drift

Run 5's control on config A suggested ≤ 0.4% drift. Three of four configs are in that
band on the metrics that matter. **One is not.**

| Config | worst drift | `ttft_p95` canonical → diagnostic |
|---|---|---|
| F | 0.60% | 1.360 → 1.356 (−0.29%) |
| H | 1.22% | 0.542 → 0.545 (+0.55%) |
| K | 2.66% | 1.885 → 1.889 (+0.21%) |
| **J** | **18.30%** | **0.705 → 0.834 (+18.30%)** |

**J's `ttft_p95` is not reproducible at the level the control implied.** Throughput,
hit rate and both e2e percentiles reproduce to ≤ 0.14% on J; only its first-token tail
moved. This matters directly: run 6 scored J's `ttft_p95` at +32.5% against the
canonical 0.705 s. Against this re-run's 0.834 s the same unchanged prediction (0.934 s)
would be **+12.0% — inside the v2 absolute limb, a pass.**

One re-run does not establish which value is correct, and **run 6's verdict stands as
published**. But J's tail has run-to-run variability an order of magnitude larger than
config A's, and any future claim resting on it needs repeated measurement first.
Recorded, not reconciled.

---

## 2. Overlap verdicts

| Config | sim top-5% `ttft` rids | real top-5% `ttft` rids | overlap | verdict |
|---|---|---|---|---|
| **F** | 163, 166, 167, 186, 187, 188, 189, 190, 191 | 167, 168, 184, 186, 187, 188, 189, 190, 191 | **7/9** | SAME requests, magnitude problem |
| **J** | 14, 18, 19, 186, 187, 188, 189, 190, 191 | 15, 19, 20, 186, 187, 188, 189, 190, 191 | **7/9** | SAME requests, magnitude problem |
| **K** | 166, 167, 168, 169, 187, 188, 189, 190, 191 | 166, 167, 168, 169, 187, 188, 189, 190, 191 | **9/9** | SAME requests, magnitude problem |
| **H** | 13, 14, 15, 16, 17, 18, 19, 20, 178 | 15, 16, 18, 19, 20, 167, 178, 179, 180 | **6/9** | SAME requests, magnitude problem |

K is an exact match — the same nine requests, in the same order of severity. F and J
agree on seven of nine, both disagreeing only at the boundary of the set. H agrees on
six of nine and is the one config whose slow set is **not** the last arrivals: H's tail
is requests 13–20, the *first* turn-0 burst.

**The next hypothesis class is therefore magnitude, not scheduling.** The model has the
right requests waiting; it charges them too much.

---

## 3. Bucket tables

### Mean `ttft` (sim − real), by turn

| turn | n | F | J | K | H |
|---|---|---|---|---|---|
| 0 | 14 | **+0.151** | **+0.151** | **+0.127** | **+0.166** |
| 1 | 24 | +0.020 | +0.027 | +0.030 | +0.040 |
| 2 | 24 | +0.016 | +0.015 | +0.014 | +0.016 |
| 3 | 24 | +0.002 | +0.001 | −0.000 | +0.002 |
| 4 | 24 | +0.003 | −0.003 | −0.012 | −0.003 |
| 5 | 24 | −0.006 | −0.015 | −0.006 | −0.018 |
| 6 | 24 | **+0.181** | +0.004 | **+0.137** | +0.006 |
| 7 | 24 | **+0.197** | **+0.141** | **+0.159** | −0.001 |

### Mean `ttft` (sim − real), by arrival quintile

| quintile | n | F | J | K | H |
|---|---|---|---|---|---|
| 0 | 37 | +0.071 | +0.075 | +0.068 | +0.089 |
| 1 | 31 | +0.011 | +0.011 | +0.010 | +0.011 |
| 2 | 51 | −0.002 | −0.006 | −0.010 | −0.007 |
| 3 | 35 | +0.017 | −0.010 | +0.039 | −0.009 |
| 4 | 28 | **+0.307** | **+0.135** | **+0.210** | +0.013 |

### Mean `ttft` (sim − real), by prompt length (config F, representative)

| prompt_len bucket | n | mean diff |
|---|---|---|
| 1k | 14 | +0.151 s |
| 2k | 70 | +0.014 s |
| 3k | 53 | +0.007 s |
| 4k | 45 | +0.191 s |

The error is **bimodal in every cut**: the shortest prompts (turn 0) and the longest,
latest ones. The middle — turns 2–5, quintiles 1–3, prompts of 2–3k — is accurate to
within 20 ms.

---

## 4. Worst-offender rows, verbatim

### F — 10 most over-predicted

```
rid= 166 turn=6 sess=  5 arr=  127.1 plen= 4084 sim=  2.570 real=  1.021 diff= +1.549 cached= 1200 pre=0
rid= 186 turn=7 sess= 17 arr=  153.2 plen= 4336 sim=  2.552 real=  1.381 diff= +1.171 cached= 1200 pre=0
rid= 188 turn=7 sess=  6 arr=  154.3 plen= 4532 sim=  4.063 real=  2.968 diff= +1.095 cached= 1200 pre=0
rid= 189 turn=7 sess= 13 arr=  155.1 plen= 4592 sim=  4.941 real=  3.892 diff= +1.049 cached= 1200 pre=0
rid= 167 turn=6 sess=  3 arr=  127.1 plen= 4081 sim=  2.970 real=  2.097 diff= +0.873 cached= 1200 pre=0
rid= 163 turn=6 sess=  2 arr=  124.7 plen= 4196 sim=  2.102 real=  1.320 diff= +0.782 cached= 1200 pre=0
rid= 190 turn=7 sess=  1 arr=  155.7 plen= 4980 sim=  5.824 real=  5.051 diff= +0.773 cached= 1200 pre=0
rid= 164 turn=6 sess=  9 arr=  125.9 plen= 3906 sim=  2.080 real=  1.339 diff= +0.742 cached= 1200 pre=0
rid= 165 turn=6 sess= 14 arr=  127.1 plen= 4276 sim=  1.732 real=  1.033 diff= +0.699 cached= 3872 pre=0
rid=  17 turn=0 sess=  0 arr=   10.7 plen= 1920 sim=  0.933 real=  0.359 diff= +0.575 cached= 1200 pre=0
```

### F — 10 most under-predicted

```
rid= 191 turn=7 sess= 14 arr=  156.0 plen= 4737 sim=  5.518 real=  5.821 diff= -0.303 cached= 1200 pre=0
rid=  15 turn=0 sess= 21 arr=    8.7 plen= 1920 sim=  0.733 real=  0.870 diff= -0.137 cached= 1200 pre=0
rid=  16 turn=0 sess=  9 arr=    8.7 plen= 1920 sim=  0.698 real=  0.835 diff= -0.137 cached= 1200 pre=0
rid= 178 turn=7 sess= 20 arr=  141.0 plen= 4666 sim=  0.708 real=  0.790 diff= -0.082 cached= 4208 pre=0
rid= 179 turn=7 sess= 16 arr=  141.0 plen= 4483 sim=  0.663 real=  0.745 diff= -0.082 cached= 3984 pre=0
rid= 151 turn=6 sess= 23 arr=  109.1 plen= 4108 sim=  0.267 real=  0.348 diff= -0.082 cached= 3680 pre=0
rid= 105 turn=4 sess=  9 arr=   77.1 plen= 3238 sim=  0.319 real=  0.391 diff= -0.071 cached= 2864 pre=0
rid=  89 turn=3 sess=  9 arr=   68.4 plen= 2865 sim=  0.325 real=  0.392 diff= -0.068 cached= 2416 pre=0
rid=  71 turn=2 sess= 20 arr=   56.5 plen= 2562 sim=  0.255 real=  0.319 diff= -0.063 cached= 2224 pre=0
rid=  97 turn=4 sess=  0 arr=   72.7 plen= 3178 sim=  0.297 real=  0.360 diff= -0.063 cached= 2752 pre=0
```

### K — 10 most over-predicted (exact 9/9 overlap config)

```
rid= 186 turn=7 sess= 17 arr=  153.2 plen= 4336 sim=  2.552 real=  1.377 diff= +1.175 cached= 1200 pre=0
rid= 187 turn=7 sess= 19 arr=  153.8 plen= 4668 sim=  3.682 real=  2.543 diff= +1.139 cached= 1200 pre=0
rid= 189 turn=7 sess= 13 arr=  155.1 plen= 4592 sim=  4.940 real=  3.880 diff= +1.060 cached= 1200 pre=0
rid= 190 turn=7 sess=  1 arr=  155.7 plen= 4980 sim=  6.044 real=  5.043 diff= +1.001 cached= 1200 pre=0
rid= 177 turn=7 sess=  9 arr=  140.9 plen= 4360 sim=  1.052 real=  0.253 diff= +0.799 cached= 3904 pre=0
rid= 163 turn=6 sess=  2 arr=  124.7 plen= 4196 sim=  2.102 real=  1.319 diff= +0.782 cached= 1200 pre=0
rid= 164 turn=6 sess=  9 arr=  125.9 plen= 3906 sim=  2.080 real=  1.337 diff= +0.743 cached= 1200 pre=0
rid= 165 turn=6 sess= 14 arr=  127.1 plen= 4276 sim=  2.582 real=  1.889 diff= +0.692 cached= 1200 pre=0
rid= 166 turn=6 sess=  5 arr=  127.1 plen= 4084 sim=  3.420 real=  2.756 diff= +0.664 cached= 1200 pre=0
rid= 156 turn=6 sess= 18 arr=  115.8 plen= 4176 sim=  0.837 real=  0.220 diff= +0.617 cached= 2208 pre=0
```

### J — 10 most over-predicted

```
rid= 188 turn=7 sess=  6 arr=  154.3 plen= 4532 sim=  3.015 real=  2.000 diff= +1.015 cached= 1200 pre=0
rid= 186 turn=7 sess= 17 arr=  153.2 plen= 4336 sim=  2.354 real=  1.380 diff= +0.974 cached= 1200 pre=0
rid= 189 turn=7 sess= 13 arr=  155.1 plen= 4592 sim=  3.893 real=  2.921 diff= +0.972 cached= 1200 pre=0
rid= 187 turn=7 sess= 19 arr=  153.8 plen= 4668 sim=  1.784 real=  1.032 diff= +0.752 cached= 4192 pre=0
rid=  17 turn=0 sess=  0 arr=   10.7 plen= 1920 sim=  0.933 real=  0.356 diff= +0.577 cached= 1200 pre=0
rid=  18 turn=0 sess= 17 arr=   10.7 plen= 1920 sim=  1.235 real=  0.659 diff= +0.575 cached= 1200 pre=0
rid=  14 turn=0 sess= 14 arr=    8.4 plen= 1920 sim=  1.011 real=  0.491 diff= +0.519 cached= 1200 pre=0
rid= 177 turn=7 sess=  9 arr=  140.9 plen= 4360 sim=  0.608 real=  0.252 diff= +0.356 cached= 3904 pre=0
rid= 165 turn=6 sess= 14 arr=  127.1 plen= 4276 sim=  0.546 real=  0.222 diff= +0.324 cached= 3872 pre=0
rid=  10 turn=0 sess= 10 arr=    7.2 plen= 1920 sim=  0.630 real=  0.338 diff= +0.292 cached= 1200 pre=0
```

### H — 10 most over-predicted

```
rid=  17 turn=0 sess=  0 arr=   10.7 plen= 1920 sim=  0.933 real=  0.349 diff= +0.585 cached= 1200 pre=0
rid=  18 turn=0 sess= 17 arr=   10.7 plen= 1920 sim=  1.235 real=  0.653 diff= +0.582 cached= 1200 pre=0
rid=  14 turn=0 sess= 14 arr=    8.4 plen= 1920 sim=  1.011 real=  0.504 diff= +0.507 cached= 1200 pre=0
rid= 177 turn=7 sess=  9 arr=  140.9 plen= 4360 sim=  0.608 real=  0.240 diff= +0.368 cached= 3904 pre=0
rid= 165 turn=6 sess= 14 arr=  127.1 plen= 4276 sim=  0.546 real=  0.224 diff= +0.322 cached= 3872 pre=0
rid=  10 turn=0 sess= 10 arr=    7.2 plen= 1920 sim=  0.630 real=  0.350 diff= +0.281 cached= 1200 pre=0
rid=  19 turn=0 sess=  1 arr=   11.0 plen= 1920 sim=  0.969 real=  0.704 diff= +0.265 cached= 1200 pre=0
rid=  12 turn=0 sess= 20 arr=    7.8 plen= 1920 sim=  0.626 real=  0.364 diff= +0.262 cached= 1200 pre=0
rid=  31 turn=1 sess= 22 arr=   23.0 plen= 2340 sim=  0.481 real=  0.229 diff= +0.252 cached= 1920 pre=0
rid=  13 turn=0 sess= 23 arr=    8.1 plen= 1920 sim=  0.669 real=  0.432 diff= +0.238 cached= 1200 pre=0
```

---

## 5. Interpretation, one paragraph per config

**F (4,607 blocks, `ttft_p95` +52.9%).** Seven of nine tail requests match. Nine of the
ten worst offenders are turn-6 and turn-7 requests with 3.9–5.0k prompts and
`cached=1200`, over-predicted by 0.7–1.5 s each. F has **25 requests capped at 1,200**,
11 of them at later turns, and they carry a mean error of +0.391 s against +0.014 s for
every other request. F's turn-6 and turn-7 buckets are the worst in the set (+0.181 and
+0.197 s). Its `ttft_p95` failure is entirely this cohort: the simulator has evicted
those sessions' history down to the shared prefix and charges a ~3,000-token recompute
that the real engine does not pay.

**J (5,089 blocks, `ttft_p95` +32.5% canonical / +12.0% against the re-run).** The same
shape, one notch milder: **18 requests capped**, only 4 at later turns, mean capped
error +0.268 s. J's turn-6 bucket is clean (+0.004 s) while turn-7 is not (+0.141 s) —
the eviction cliff has only just started to bite at this pool size. J is also the config
whose measurement moved 18.3% between runs, so its position on the pass/fail line is
the least certain of the four.

**K (4,246 blocks, `ttft_p95` +37.0%).** The cleanest diagnosis: **9 of 9 tail requests
match exactly**, in the same severity order. K has the largest capped cohort, **28
requests, 14 of them at later turns** — the most of any config, matching its position as
the smallest pool. Both turn-6 (+0.137 s) and turn-7 (+0.159 s) are bad. K is F's
failure with more of it.

**H (5,811 blocks, `ttft_p95` +20.3%).** Different, and this is the important one.
H's slow set is the **turn-0 burst (rids 13–20), not the last arrivals** — its
quintile-4 error is +0.013 s, essentially zero, and its turn-6 and turn-7 buckets are
+0.006 and −0.001 s. **H has 14 capped requests and all 14 are turn 0**: zero
later-turn evictions, because at 5,811 blocks there is nothing to evict. H's entire
residual is the cold-start component. This is the direct, per-request confirmation of
run 7's prediction (iii) — H's miss was never a cache effect, and no eviction change
could have touched it.

---

## 6. Joint hypothesis — the four diagnoses do agree

**The residual `ttft_p95` error is one cohort with two causes, and both are magnitude
errors on prefill, not scheduling errors.**

`cached=1200` is not arbitrary: the trace's sessions share exactly **1,200 words = 75
blocks** of system prompt before diverging. A request capped at 1,200 is one where the
simulator matched the shared prefix and **nothing else**.

**Component 1 — cold start, pool-independent.** All 24 turn-0 requests legitimately
cap at 1,200 (they have no session history to match), and 14 survive `--drop-first 10`.
The simulator over-predicts their TTFT by **+0.13 to +0.17 s in every config including
H**, where no eviction happens at all. This is a fixed over-charge on first-turn prefill,
present at every pool size, and it is the whole of H's failure.

**Component 2 — eviction cliff, strictly pool-dependent.** Later-turn requests that
*should* match their session history but fall back to 1,200:

| Config | blocks | later-turn capped |
|---|---|---|
| H | 5,811 | **0** |
| J | 5,089 | **4** |
| F | 4,607 | **11** |
| K | 4,246 | **14** |

**Perfectly monotonic in pool size.** These requests are charged a full ~3,000-token
recompute; the real engine evidently still matches most of their prefix. (This is
inferred from TTFT — `bench.py` does not report per-request cached tokens, so the real
side's match length is not directly measured. That is the obvious next instrument.)

**Why runs 6 and 7 could not move this.** Hit rate is a token-weighted mean over 182
requests, dominated by the 155–170 that match correctly; the tail is set by the 14–28
that fall off the cliff. v0.6 and v0.7 both shifted the aggregate — hit-rate error is
now 0.19% — without changing *which* requests fall off. That is exactly what §2's
"same requests" verdict says, and it explains why two opposed cache changes left F, G,
H and J bit-identical.

**What this implies for the next change** (not made here, and not a prediction):
component 2 is an eviction-*policy* question — which blocks survive for a session
between its turns — and component 1 is a flat prefill over-charge on cold requests
that no cache work will reach. They are separable and should be attacked separately.
The `cached=1200` count per config is a direct, cheap diagnostic for component 2, and
`bench.py` reporting per-request cached tokens would make the comparison a measurement
rather than an inference.
