# JMODES_REPORT — what separates config J's two `ttft_p95` modes

**Date:** 2026-08-29  
**Existing data only** — the 14 per-request dumps from the noise batch. No GPU, no new runs, no simulator or `perf.json` change, nothing re-scored.

`LADDER_REPORT.md` found config J bimodal in `ttft_p95` while C, K and A are each a single tight cluster. This splits J's runs at the gap and asks which requests actually move.

## The split

Sorted `ttft_p95` across the 14 clean J repeats:

```
  0.700  0.702  0.828  0.830  0.832  0.833  0.834  0.839  0.840  0.840  0.842  0.842  0.842  0.842
```
The largest gap is between 0.702 and 0.828; the split is taken at 0.765 s. **Low mode: 2 runs** (reps 10, 14). **High mode: 12 runs.**

| mode | n | mean `ttft_p95` | mean throughput | mean hit rate |
|---|---|---|---|---|
| low | 2 | 0.7010 s | 203.9 tok/s | 0.842 |
| high | 12 | 0.8370 s | 203.9 tok/s | 0.842 |

## Which requests differ

Mean TTFT per request in each mode, over the 182 requests that survive `--drop-first 10`, sorted by absolute difference:

| rid | low-mode TTFT | high-mode TTFT | high − low | in 8a cliff cohort? |
|---|---|---|---|---|
| 19 | 0.7011 s | 1.0091 s | **+0.3080 s** | **yes** |
| 17 | 0.3457 s | 0.5315 s | **+0.1858 s** | **yes** |
| 37 | 0.1488 s | 0.3182 s | **+0.1694 s** | no |
| 68 | 0.3603 s | 0.3189 s | **-0.0414 s** | no |
| 38 | 0.3690 s | 0.3286 s | **-0.0404 s** | no |
| 165 | 0.2229 s | 0.2582 s | **+0.0353 s** | no |
| 29 | 0.3567 s | 0.3308 s | **-0.0259 s** | no |
| 135 | 0.3020 s | 0.3183 s | **+0.0163 s** | no |
| 40 | 0.4983 s | 0.4850 s | **-0.0134 s** | no |
| 41 | 0.4763 s | 0.4634 s | **-0.0130 s** | no |
| 151 | 0.3560 s | 0.3440 s | **-0.0120 s** | no |
| 20 | 0.9596 s | 0.9478 s | **-0.0117 s** | **yes** |
| 96 | 0.1920 s | 0.2036 s | **+0.0115 s** | no |
| 143 | 0.2374 s | 0.2489 s | **+0.0115 s** | no |
| 150 | 0.2784 s | 0.2671 s | **-0.0113 s** | no |

3 of 182 requests move by more than 50 ms; the remaining 179 differ by a mean of 0.0041 s — flat.

## Do the movers match the run-8a eviction-cliff cohort?

Run 8a identified the cohort whose simulated prefix match collapses to exactly 1200 tokens — the shared system prompt, where sessions diverge. In `simpr_J.jsonl` that cohort is **27 requests**.

- requests moving >50 ms between J's modes: **3**
- of those, in the cliff cohort: **2** (67% of movers)
- cliff-cohort requests that do NOT move: **25**

Movers: `[17, 19, 37]`
Cliff cohort: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 186, 188, 189, 190]`

## Observation

The two modes are not a global shift. 3 of 182 requests carry 48% of the total per-request difference, the largest being rid 19 at +0.308 s, while everything else is flat to within tens of milliseconds. 
2 of 3 movers fall in the run-8a cliff cohort. That is above the base rate — the cohort is 27/182 = 15% of requests, so chance alone would put 0.4 of 3 movers in it — but with only 3 movers this is far too small a sample to call an association, and it points the other way too: 25 of the 27 cohort members do not move at all. Being in the cohort is plainly not sufficient.
 All 3 movers sit early in the trace (rids 17, 19, 37), as does most of the cohort, so position and cohort membership are confounded here and this data cannot separate them.
 This is a measurement of which requests differ; it proposes no mechanism and recommends no change.

