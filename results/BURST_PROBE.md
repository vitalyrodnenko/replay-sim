# BURST_PROBE — service order under a 12-request simultaneous burst

**Date:** 2026-08-29  
**Diagnostic. No predictions were frozen, no verdict, no fix proposed.**  
**No simulator, `perf.json`, or verdict change.**

## What was run

`results/trace_burst.jsonl` — 12 requests, **all with `arrival_s = 0.0`**, prompt lengths alternating 700 / 2,600 tokens over the shared prefix. Config A, standard protocol (strict drain, pool asserted 87,200), `--per-request`, **no `--drop-first`**: in a 12-request burst every request is the subject.

> **Note on the spec.** A ~700-token prompt cannot contain a 1,200-token shared prefix. Resolved as: short prompts are 700 tokens sharing the *first 700 words* of the common prefix; long prompts are 2,600 = the full 1,200-word prefix + 1,400 unique. Every request still shares a real prefix with every other. Verified word-by-word against `results/trace.jsonl`.

## Ordered by real TTFT

| order | rid | prompt_len | arrival order | real TTFT | sim TTFT |
|---|---|---|---|---|---|
| 1 | 0 | 700 | 0 | **0.320 s** | 1.695 s |
| 2 | 1 | 2,600 | 1 | **1.175 s** | 2.543 s |
| 3 | 2 | 700 | 2 | **1.175 s** | 2.543 s |
| 4 | 3 | 2,600 | 3 | **2.023 s** | 4.240 s |
| 5 | 4 | 700 | 4 | **2.023 s** | 4.240 s |
| 6 | 6 | 700 | 6 | **2.876 s** | 5.938 s |
| 7 | 5 | 2,600 | 5 | **2.876 s** | 5.089 s |
| 8 | 10 | 700 | 10 | **3.729 s** | 8.232 s |
| 9 | 7 | 2,600 | 7 | **3.730 s** | 6.787 s |
| 10 | 8 | 700 | 8 | **3.730 s** | 6.787 s |
| 11 | 9 | 2,600 | 9 | **3.730 s** | 8.232 s |
| 12 | 11 | 2,600 | 11 | **4.080 s** | 8.252 s |

## Service order is stepped, and the steps are one prefill batch wide

The 12 requests do not finish at 12 distinct times. They land on **6 levels**, requests within a level sharing a TTFT to within 50 ms:

| level | real TTFT | rids | prompt lengths |
|---|---|---|---|
| 1 | 0.320 s | 0 | 700 |
| 2 | 1.175 s | 1, 2 | 2600, 700 |
| 3 | 2.023 s | 3, 4 | 2600, 700 |
| 4 | 2.876 s | 6, 5 | 700, 2600 |
| 5 | 3.729 s | 10, 7, 8, 9 | 700, 2600, 700, 2600 |
| 6 | 4.080 s | 11 | 2600 |

Consecutive levels are separated by 0.855, 0.848, 0.853, 0.854, 0.350 s. `perf.json` prices a full `max-num-batched-tokens` prefill batch at `b_p × 2048` = **0.835 s**, which is the step size to within a few milliseconds.

## Observation

The engine served this burst **first-come-first-served, batched into fixed-token prefill steps** — not shortest-first, and not by any ordering that looks at prompt length. Ranked by measured TTFT the requests come out in arrival order for 9 of 11 adjacent pairs, while prompt length is monotone for only 7 of 11: the 700-token and 2,600-token prompts are interleaved through the completion order exactly as they were submitted, and a short request queued behind a long one waits for it rather than overtaking. What structures the result is not the ordering but the batching: TTFTs collapse onto 6 discrete levels 0.83 s apart, one full 2,048-token chunked-prefill step per level, so several requests become schedulable together and are reported ready together. The simulator reproduces that ordering and that step structure while over-predicting every TTFT by roughly a factor of two — the ranking is right and the magnitude is not, which is the same signature run 8a recorded. This is a diagnostic for run 9 design; no mechanism is claimed and no change is proposed.

