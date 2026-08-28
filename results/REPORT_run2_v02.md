# replay-sim v0.2 validation report — run 2

**Date:** 2026-08-27
**Verdict (held-out configs D and E):** **FAIL** — 9 of 12 rows within the 15-point bar.
**Bottom line:** v0.2 is a large, real improvement — mean absolute error on the in-sample
configs fell from **103.3% to 14.5%**, and the config-C sign error is gone. The scheduler
axis (D) passes cleanly at 6/6. What still fails is **tail latency on the pool axis**, and
one of the three failures is marginal (15.0 pt against a 15.0 pt bar).

---

## 1. Environment

Unchanged from run 1 except the simulator version. Full capture:
`results/logs/environment.txt`.

| | |
|---|---|
| GPUs | 2 × NVIDIA GeForce RTX 4090, 24,564 MiB each, compute capability 8.9 |
| Driver / CUDA | 580.173.02 / CUDA 13.0 |
| vLLM / torch / transformers | 0.28.0 / 2.13.0 / 5.16.1 |
| Model | `Qwen/Qwen3-32B-AWQ`, snapshot `0499c3ac83fdef8810b907a23894ba91e95eddd8`, AWQ 4-bit, TP=2 |
| Weights | 9.01 GiB per GPU |
| Simulator | **v0.2** (commit `7e1d482`) |
| Trace | unchanged from run 1, `sha256 4e70250f…` — 192 requests, 607,756 prompt tokens, 156 s span |

GPU utilisation during the five runs: A 93.8%, B 98.4%, C 94.9%, D 93.8/93.1%, E 94.1%.
All runs were GPU-bound.

### v0.2 drop-in

Only the four files named in the handoff were replaced: `simulator.py`, `calibrate.py`,
`bench.py`, `README.md`. **`workload.py` was deliberately not replaced** — the archive
ships the *pristine pre-fix* version with the `tok0..tok511` vocabulary, and copying it
would have silently reverted the approved tokenizer fix and broken the provenance of the
committed trace. Verified after the swap: `workload.py` still regenerates
`results/trace.jsonl` byte-identically. `compare.py`, `RUNBOOK.md` and `__init__.py` in
the archive were byte-identical to what was already present.

---

## 2. What was run

1. **Recalibrated** — the decode grid changed, so `perf.json` was regenerated on the same
   model and hardware and committed (`55de5f6`) before any prediction.
2. **Predicted all five configs** with v0.2, KV capacity read from each config's own
   server startup log. Committed at `43fe037`; **freeze absolute from that commit.**
3. **Real runs, held-out first**: D, E, then A, B, C. Fresh server per config, readiness
   polled on `/health`, `--drop-first 10` on every run.
4. **Compared** — held-out (`results/compare_heldout.txt`) decides the verdict; in-sample
   (`results/compare_insample.txt`) reported separately.

### Recalibration, and one thing it broke

```
prefill  256/512/1024/2048/4096  ->  110.8 / 211.5 / 422.4 / 840.6 / 1718.4 ms
decode B=1,8,32 ctx=512          ->  13.39 / 15.60 / 21.47 ms/step
decode B=8 ctx=4096              ->  18.79 ms/step
decode B=32 ctx=2048             ->  22.56 ms/step
decode B=64/96 ctx=512           ->  31.49 / 46.30 ms/step      (new in v0.2)
decode B=128 ctx=256             ->  58.39 ms/step              (new in v0.2)

            a          b_p          b_d          c_kv
v0 run 1  0.014146   0.00041879   0.00018597   0.047886
v0.2      0.012686   0.00041896   0.00034517   0.0
```

`b_d` nearly doubled, which is the intended effect — the saturated-batch points absorb the
TP all-reduce cost v0 was missing.

> **Finding, recorded before any prediction and not corrected: `c_kv` fitted to exactly
> 0.0.** The three new large-batch/small-context points let batch size absorb all the
> variance, the KV term fits negative, and `max(c_kv, 0.0)` clamps it away. **Decode step
> time in v0.2 therefore has no context-length dependence at all** — even though the grid
> itself shows some: at B=8, 15.60 ms at ctx 512 versus 18.79 ms at ctx 4096, implying a
> c_kv near 0.111. Two grid points share kv = 32,768 with step times of 18.79 ms and
> 58.39 ms, which is exactly what makes kv a poor regressor once batch dominates the
> design. See §5.1 — this is the leading explanation for the one metric that got worse.

### Predicted-with N versus actually-run N

KV capacity was probed per config before predicting; A and C were re-probed rather than
reusing run 1's numbers, since `--max-num-seqs` changes CUDA-graph memory.

| Config | util | max-num-seqs | predicted-with N | run N | Match |
|---|---|---|---|---|---|
| A | 0.85 | 128 | 5,450 | 5,450 (87,200 tok) | ✅ exact |
| B | 0.85 | 128 | 5,450 | 5,450 (87,200 tok) | ✅ exact |
| C | 0.60 | 128 | 2,440 | 2,440 (39,040 tok) | ✅ exact |
| **D** | 0.85 | **32** | **5,176** | **5,490 (87,840 tok)** | ❌ **+6.1%** |
| E | 0.70 | 128 | 3,644 | 3,644 (58,304 tok) | ✅ exact |

> **Finding, not corrected (freeze was absolute).** Config D's probe reported 82,816 KV
> tokens; the actual run allocated **87,840**. This is the same non-deterministic pool
> sizing documented in run 1 §5.2, now observed at 0.85 with `--max-num-seqs 32` — a
> setting that was *deterministic* at `--max-num-seqs 128` (87,200 twice in run 1, 87,200
> again here). D was therefore predicted against a pool 6.1% **smaller** than the one it
> ran on.
>
> Does it change the D verdict? No, and the reason is structural rather than lucky: v0.2
> predicts D ≡ A because neither the pool nor the sequence cap binds at this trace's
> concurrency. A pool 6.1% *larger* than predicted is even further from binding, so the
> prediction's logic is unaffected. But the mismatch is real and is reported as found.

---

## 3. Held-out results — these decide the verdict

Configs A/B/C are development data: v0.2 was designed while looking at their run-1
results. Only D and E are held out.

### D vs A — scheduler axis — **6 / 6 OK**

v0.2 made an unusually sharp claim: `--max-num-seqs 32` changes **nothing**, predicting
+0.0% on every metric. This was verified before the run to be a genuine prediction rather
than a mis-parameterisation — the trace's concurrency never approaches 32, so the cap is
inert. Measurement agreed.

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| ttft_p50_s | +0.0% | +0.0% | **0.0 pt** | ✅ OK |
| ttft_p95_s | +0.0% | −7.2% | **7.2 pt** | ✅ OK |
| e2e_p50_s | +0.0% | −0.7% | **0.7 pt** | ✅ OK |
| e2e_p95_s | +0.0% | −4.2% | **4.2 pt** | ✅ OK |
| throughput_tok_s | +0.0% | +0.4% | **0.4 pt** | ✅ OK |
| prefix_cache_hit_rate | +0.0% | +0.4% | **0.4 pt** | ✅ OK |

### E vs A — pool axis at an unseen point — **3 / 6 OK**

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| ttft_p50_s | +34.6% | +30.5% | **4.1 pt** | ✅ OK |
| ttft_p95_s | +308.8% | +390.9% | 82.1 pt | ❌ MISS |
| e2e_p50_s | +10.2% | +25.2% | 15.0 pt | ❌ MISS *(marginal)* |
| e2e_p95_s | +110.9% | +180.1% | 69.2 pt | ❌ MISS |
| throughput_tok_s | −3.8% | −4.0% | **0.2 pt** | ✅ OK |
| prefix_cache_hit_rate | −13.5% | −15.2% | **1.7 pt** | ✅ OK |

**Held-out total: 9 of 12 rows within the bar.** The `e2e_p50` miss clears the bar by
0.04 points — `gap = 15.0426 pt` against a 15.0 pt threshold. It is a miss and is counted
as one, but it should not be read as a qualitatively different result from a pass.

### Held-out absolute values

| Metric | sim_D | real_D | err | sim_E | real_E | err |
|---|---|---|---|---|---|---|
| ttft_p50_s | 0.231 | 0.246 | −6.1% | 0.311 | 0.321 | −3.1% |
| ttft_p95_s | 0.829 | 0.604 | +37.3% | 3.389 | 3.196 | **+6.0%** |
| e2e_p50_s | 3.709 | 4.796 | −22.7% | 4.086 | 6.045 | −32.4% |
| e2e_p95_s | 5.686 | 7.217 | −21.2% | 11.989 | 21.103 | −43.2% |
| throughput_tok_s | 220.0 | 208.7 | +5.4% | 211.7 | 199.5 | +6.1% |
| prefix_cache_hit_rate | 0.862 | 0.859 | **+0.3%** | 0.746 | 0.726 | **+2.8%** |
| preemptions | 0 | 0 | ✅ | 0 | 0 | ✅ |

---

## 4. In-sample results (development data — proves nothing)

Reported for regression only. **3 of 11 rows** within the bar, against 1 of 11 in run 1.

| Row | sim Δ | real Δ | gap | Verdict |
|---|---|---|---|---|
| B vs A ttft_p50_s | +18874.5% | +22402.4% | 3528.0 pt | MISS |
| B vs A ttft_p95_s | +15301.6% | +22553.6% | 7252.0 pt | MISS |
| B vs A e2e_p50_s | +2175.8% | +1889.5% | 286.2 pt | MISS |
| B vs A e2e_p95_s | +2571.4% | +2200.7% | 370.6 pt | MISS |
| B vs A throughput_tok_s | −46.3% | −49.5% | **3.2 pt** | ✅ OK |
| C vs A ttft_p50_s | +408.2% | +470.7% | 62.5 pt | MISS |
| C vs A ttft_p95_s | +2823.0% | +4190.8% | 1367.7 pt | MISS |
| C vs A e2e_p50_s | +129.4% | +205.7% | 76.2 pt | MISS |
| C vs A e2e_p95_s | +588.2% | +467.3% | 120.9 pt | MISS |
| C vs A throughput_tok_s | −17.3% | −17.7% | **0.4 pt** | ✅ OK |
| C vs A prefix_cache_hit_rate | −30.4% | −30.3% | **0.1 pt** | ✅ OK |

The B-vs-A rows remain enormous for the reason established in run 1: config B's relative
change is measured against a config-A baseline whose *absolute* tail is small (0.651 s),
so any baseline error is amplified into thousands of points. This is a property of the
metric definition as much as of the simulator.

---

## 5. v0 → v0.2, error per metric on A/B/C

Absolute error `|sim − real| / real`, run 1 (v0) against run 2 (v0.2). Note the real runs
differ slightly between the two: run 2 uses `--drop-first 10`.

| Config | Metric | v0 error | v0.2 error | |
|---|---|---|---|---|
| A | ttft_p50_s | 25.4% | **6.1%** | better |
| A | ttft_p95_s | 867.0% | **27.3%** | better |
| A | e2e_p50_s | **2.3%** | 23.2% | **worse** |
| A | e2e_p95_s | 388.4% | **24.5%** | better |
| A | throughput_tok_s | **0.9%** | 5.9% | **worse** |
| A | prefix_cache_hit_rate | 15.2% | **0.7%** | better |
| B | ttft_p50_s | 22.8% | 20.8% | ~same |
| B | ttft_p95_s | 17.6% | **13.4%** | better |
| B | e2e_p50_s | 16.2% | **12.1%** | better |
| B | e2e_p95_s | 15.8% | **12.4%** | better |
| B | throughput_tok_s | **9.9%** | 12.7% | **worse** |
| C | ttft_p50_s | 76.1% | **16.4%** | better |
| C | ttft_p95_s | 84.5% | **13.2%** | better |
| C | e2e_p50_s | 68.4% | **42.3%** | better |
| C | e2e_p95_s | 58.0% | **8.5%** | better |
| C | throughput_tok_s | 22.5% | **6.4%** | better |
| C | prefix_cache_hit_rate | 65.7% | **0.5%** | better |

**Mean absolute error: 103.3% → 14.5%** (n = 17). 14 metrics better, 3 worse, 1 unchanged.

Delta gaps against config A, in points:

| Row | v0 gap | v0.2 gap |
|---|---|---|
| B vs A ttft_p50_s | 7471.9 | 3528.0 |
| B vs A ttft_p95_s | 15588.0 | 7252.0 |
| B vs A e2e_p50_s | 267.8 | 286.2 |
| B vs A e2e_p95_s | 1836.3 | **370.6** |
| B vs A throughput_tok_s | 4.5 | **3.2** |
| C vs A ttft_p50_s | 340.7 | **62.5** |
| C vs A ttft_p95_s | 3187.0 | **1367.7** |
| C vs A e2e_p50_s | 199.6 | **76.2** |
| C vs A e2e_p95_s | 501.7 | **120.9** |
| C vs A throughput_tok_s | 17.7 | **0.4** |
| C vs A prefix_cache_hit_rate | 30.6 | **0.1** |

### 5.1 What each v0.2 change bought

**Change 3 (cache coupled to the block pool) — the standout.** Run 1's headline defect was
a *sign error*: v0 predicted reuse would rise as the pool shrank while the engine's hit
rate collapsed. Fixed and then some:

| | config A | config C | config E (held-out) |
|---|---|---|---|
| sim hit rate | 0.862 | 0.600 | 0.746 |
| real hit rate | 0.856 | 0.597 | 0.726 |
| error | +0.7% | **+0.5%** | **+2.8%** |

The C-vs-A hit-rate delta gap went from 30.6 pt (wrong direction) to **0.1 pt**, and it
generalised to an unseen pool size at 1.7 pt. This is the strongest evidence in the run
that the fix is real physics and not a fit to the development data.

**Change 1 (blocks published during prefill).** Config A's ttft_p95 error fell from +867%
to +27.3% and e2e_p95 from +388% to −24.5%. The manufactured tail is gone.

**Change 2 (routine preemption).** v0 predicted zero preemptions everywhere. v0.2 predicts
11 (B) and 16 (C) against measured 9 and 10 — the right order of magnitude and, more
importantly, the right *set*: zero predicted and zero measured for A, D and E.

**Change 6 (extended decode grid) — mixed.** It doubled `b_d` and improved config B's
latency errors by 2–4 points each. But it also collapsed `c_kv` to zero, and that is the
best explanation for the one clear regression: **config A e2e_p50 went from 2.3% error to
23.2%, in the direction of the simulator being too fast.** With `c_kv = 0`, decode steps
cost the same at 4,000 tokens of context as at 400, so the long-context tail of the trace
decodes too cheaply and predicted end-to-end times run short. The same signature appears
on every held-out row: e2e_p50 −22.7% (D) and −32.4% (E), e2e_p95 −21.2% (D) and −43.2%
(E) — all under-predictions, all on the metrics most exposed to accumulated decode time.

**Change 7 (`--drop-first`) — a residual asymmetry.** `bench.py --drop-first 10` was used
on all five real runs, as instructed. The simulator has no equivalent, so **sim percentiles
cover 192 requests and real percentiles cover 182.** The dropped requests are the earliest
arrivals, which are also the ones that miss the prefix cache hardest, so the two sides are
not computing percentiles over the same population. Not corrected — noted so it is not
mistaken for physics.

---

## 6. Why the remaining misses happen

Hypotheses only. No simulator code or `perf.json` was modified before or after the runs.

### 6.1 The E tail misses are mostly a baseline artifact, not an E modelling error

`ttft_p95` for E has an *absolute* error of only **+6.0%** (3.389 s predicted, 3.196 s
measured) — one of the most accurate numbers in the whole run. Its delta still misses by
82.1 pt because the config-A baseline it is divided by is off by +27.3% (0.829 vs 0.651).
A 27% error on a 0.65 s baseline is 0.18 s in absolute terms, which is negligible
operationally and enormous once turned into a ratio against a config whose tail grew 4×.

This is the same amplification that dominated run 1, now at one twentieth the magnitude.
It argues that the 15-point bar on *relative* change is a harsh instrument when the
baseline metric is small: `compare.py` divides by a config-A tail of 0.65 s, so a
sub-second modelling error becomes a three-figure gap.

### 6.2 The `e2e` under-prediction: missing context-dependent decode cost

Every `e2e` row across A, D and E is under-predicted, by 21–43%. The single change that
would produce exactly this is `c_kv = 0.0` (§2). The trace's contexts grow from ~1,900 to
~5,000 tokens across a session's eight turns, so accumulated decode cost is precisely
where a missing context term shows up, and it shows up in `e2e` far more than in `ttft`.
Consistent with this: `ttft_p50` errors are small everywhere (−6.1% A, −6.1% D, −3.1% E)
because TTFT is dominated by prefill, where `b_p` is intact and essentially unchanged
between v0 and v0.2 (0.00041879 → 0.00041896).

**This is a calibration-design issue, not a simulator-physics issue.** The step model still
has a `c_kv` term; the extended grid simply cannot identify it. A grid that varies context
at fixed batch — rather than adding three points that all vary batch — would recover it.

### 6.3 Config B's remaining gaps

B is uniformly better than v0 (13.4% / 12.1% / 12.4% on the p95/p50 metrics versus
17.6% / 16.2% / 15.8%) but still under-predicted by ~12–21%. The extended decode grid
absorbed part of the TP all-reduce cost into `b_d`, which is why it improved; the residual
is consistent with the remaining un-modelled communication on a config that runs both GPUs
at 98.4% for five minutes.

---

## 7. Run integrity

- **Recalibration committed before any prediction** (`55de5f6`).
- **All five predictions committed before any real run** (`43fe037`), freeze absolute from
  that commit. Nothing under it was regenerated or edited; both mismatches discovered
  afterwards (D's pool, `c_kv`) are reported as findings.
- **Held-out runs executed first** (D, E), before A/B/C, so the in-sample regression could
  not influence them.
- **Server fully restarted between every run**, readiness polled on `/health`.
- **`--drop-first 10`** on all five real runs; `dropped_warmup: 10`, 182 requests scored.

### One operator error, and what it cost

The first attempt at the A/B/C batch invoked `run_config.sh A` without a utilisation
argument, so `serve.sh` fell back to the RUNBOOK's default of **0.90** rather than the
0.85 the predictions were made against. Config A died in CUDA-graph capture after 41 s —
the same non-determinism documented in run 1 — before writing any output. The loop was
stopped, verified to have produced no `real_A/B/C.json`, and A and B were re-run at 0.85.
The held-out D and E runs had already completed at their correct settings and were
untouched. No prediction was altered; this was a wrong-invocation error, not a
freeze violation.

### Teardown hygiene

`scripts/stop_server.sh` reaps orphaned `VLLM::Worker` processes as built in run 1. It
needed one further fix this run: `pkill -f` also matches the *invoking shell's* command
line, so a teardown call in a command that mentioned `replay_sim.calibrate` killed its own
caller. The script now excludes its own process ancestry before signalling.

---

## 8. Where this leaves the hypothesis

The v0.2 result is a genuine advance, and the parts that improved are the parts that
matter most for the product axis:

- **The cache/pool model is now trustworthy.** Hit rate predicted within 0.5–2.8% across
  three different pool sizes including an unseen one, with the run-1 sign error eliminated.
- **Throughput is solid on every axis**: 3.2, 0.4, 0.2 pt gaps on B, C and E.
- **The scheduler axis passes outright**, 6/6, including a correct prediction that the
  change would be a no-op.
- **Preemption is qualitatively right** for the first time.

What is left is narrower and better understood than run 1's failure:

1. **Recover `c_kv`.** Vary context at fixed batch in the calibration grid so the KV term
   is identifiable. This is the highest-value fix and it is in `calibrate.py`, not the
   simulator — it is the direct cause of the 21–43% `e2e` under-predictions and of the one
   metric that regressed from v0.
2. **Reduce the config-A tail baseline error** (+27.3% on ttft_p95). Because every delta
   divides by it, this single number gates several held-out rows at once.
3. **Add the TP communication term** — still worth ~12–21% on saturated configs.
4. **Consider whether the bar is measuring what it should.** A 0.18 s absolute error on a
   0.65 s baseline becoming an 82-point gap suggests pairing the relative-change bar with
   an absolute-error floor, so sub-second differences on fast configs stop dominating the
   verdict.

Two of the three remaining held-out misses trace back to items 1 and 2, and the third
(`e2e_p50`, 15.0 pt) misses by 0.04 points.
