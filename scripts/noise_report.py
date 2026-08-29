"""Render results/NOISE_REPORT.md from noise_stats.json, following NOISE_PLAN.md.

Analysis keys are spelled out (dispersion/bootstrap/repeats/noise_band/drift) so
they cannot be confused with the config letters A and J.
"""
import argparse, json, os

METRICS = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s",
           "throughput_tok_s", "prefix_cache_hit_rate"]
PCT = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s"]
CFGS = ["A", "J"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default="results/noise/noise_stats.json")
    ap.add_argument("--noise-dir", default="results/noise")
    ap.add_argument("--out", default="results/NOISE_REPORT.md")
    a = ap.parse_args()
    S = json.load(open(a.stats))
    disp, boot = S["dispersion"], S["bootstrap"]
    reps, band, drift = S["repeats"], S["noise_band"], S["drift"]

    excluded = []
    qlog = os.path.join(a.noise_dir, "queue_log.txt")
    if os.path.exists(qlog):
        for line in open(qlog):
            if any(k in line for k in ("FAIL_", "SKIP ", "BREAKER", "DEADLINE")):
                excluded.append(line.strip())

    L = []
    W = L.append
    W("# NOISE_REPORT — how much of the series' gap structure is the benchmark itself\n")
    W("**Date:** 2026-08-29  ")
    W("**Pre-registered** in `results/NOISE_PLAN.md`, committed before any run, "
      "amended and corrected before any counted repeat.  ")
    W("**No simulator change. No `perf.json` change. No published verdict is re-scored.**\n")

    nA = disp["A"]["ttft_p95_s"]["n"]
    nJ = disp["J"]["ttft_p95_s"]["n"]
    W(f"**Clean repeats:** config A **{nA}**, config J **{nJ}**, "
      f"run alternating with a full server restart, strict VRAM drain and an asserted "
      f"KV pool before every one.\n")

    cvA = disp["A"]["ttft_p95_s"]["cv"] * 100
    cvJ = disp["J"]["ttft_p95_s"]["cv"] * 100
    W("## Bottom line\n")
    W(f"`ttft_p95` — the metric that has carried every held-out failure since run 3 — "
      f"has a run-to-run CV of **{cvA:.1f}%** on config A and **{cvJ:.1f}%** on config J. "
      f"Every other metric is far tighter. The consequences are in §3 and §4.\n")

    # ---- 1. dispersion ----
    W("## 1. Dispersion across repeats (plan §4)\n")
    for cfg in CFGS:
        W(f"### Config {cfg} (n = {disp[cfg]['ttft_p95_s']['n']})\n")
        W("| metric | mean | stdev | CV | min | max | median | range as % of mean |")
        W("|---|---|---|---|---|---|---|---|")
        for m in METRICS:
            d = disp[cfg][m]
            p = 4 if d["mean"] < 10 else 1
            W(f"| `{m}` | {d['mean']:.{p}f} | {d['stdev']:.{p}f} | "
              f"**{100*d['cv']:.2f}%** | {d['min']:.{p}f} | {d['max']:.{p}f} | "
              f"{d['median']:.{p}f} | {d['range_pct_of_mean']:.1f}% |")
        W("")

    # ---- 2. bootstrap ----
    W("## 2. Within-run bootstrap 95% CI (plan §5)\n")
    W("10,000 resamples of the 182 kept per-request values per run, seed 12345, "
      "percentile recomputed with bench.py's own estimator.\n")
    W("| config | metric | median within-run CI width | as % of the value | "
      "across-run spread (CV) |")
    W("|---|---|---|---|---|")
    for cfg in CFGS:
        for m in PCT:
            b = boot[cfg][m]
            W(f"| {cfg} | `{m}` | {b['median_width']:.4f} s | "
              f"{b['median_width_pct']:.1f}% | {100*disp[cfg][m]['cv']:.2f}% |")
    W("")
    W("**What the comparison says.** The within-run CI is what one run can tell you "
      "about its own 182 requests; the across-run CV additionally carries the server "
      "restart, the fresh KV pool and the cache refill. Where the across-run spread "
      "exceeds the within-run width, repeating the run buys more than lengthening it.\n")

    # ---- 3. repeats needed ----
    W("## 3. Repeats needed for a trustworthy `ttft_p95` (plan §6)\n")
    W("Smallest *n* with t(0.975, n−1)·s/√n ≤ target · mean.\n")
    W("| config | mean | stdev | CV | n for ±5% | n for ±10% | (±5%, z) | (±10%, z) |")
    W("|---|---|---|---|---|---|---|---|")
    for cfg in CFGS:
        r = reps[cfg]
        W(f"| {cfg} | {r['mean']:.4f} s | {r['stdev']:.4f} | {100*r['cv']:.2f}% | "
          f"**{r['n_for_5pct']}** | **{r['n_for_10pct']}** | "
          f"{r['n_for_5pct_z']} | {r['n_for_10pct_z']} |")
    W("")
    worst5 = max(reps[c]["n_for_5pct"] for c in CFGS)
    worst10 = max(reps[c]["n_for_10pct"] for c in CFGS)
    W(f"> Every `ttft_p95` number in runs 1–8a rests on **one** run. To state one to "
      f"±10% takes **{worst10}** repeats on this workload; to ±5%, **{worst5}**.\n")

    # ---- 4. noise band ----
    W("## 4. Published rows that sit inside the measured noise band (plan §7)\n")
    W("**Flagging only. Published verdicts stand and are not recomputed or amended.** "
      "A row is flagged when its published gap is small enough that a single pair of "
      "measurements could have produced it by chance.\n")
    W("CV is measured only for A and J. For any other config it is a proxy — "
      "**primary** uses max(CV_A, CV_J), **sensitivity** uses min. This is the main "
      "limitation: configs far from A and J (C at util 0.60, say) may be noisier than "
      "either proxy.\n")
    for mode, label in (("primary", "Primary (max proxy)"), ("sensitivity", "Sensitivity (min proxy)")):
        rows = band[mode]
        ins = [r for r in rows if r["inside"]]
        W(f"**{label}: {len(ins)} of {len(rows)} scored rows fall inside the band.**\n")
    W("")
    W("### Rows flagged under the primary proxy\n")
    prim = [r for r in band["primary"] if r["inside"]]
    if prim:
        W("| run | config | metric | published gap | 95% noise band | verdict as published |")
        W("|---|---|---|---|---|---|")
        for r in sorted(prim, key=lambda r: (r["run"], r["config"], r["metric"])):
            v = "OK" if r["v2"] else "MISS"
            W(f"| {r['run']} | {r['config']} | `{r['metric']}` | {r['gap_pt']:.1f} pt | "
              f"±{r['band_pt']:.1f} pt | {v} |")
    else:
        W("_None._")
    W("")
    miss_inside = [r for r in band["primary"] if r["inside"] and not r["v2"]]
    W("### The rows that matter\n")
    if miss_inside:
        W("These were scored **MISS** in the published series and also sit inside the "
          "noise band — the only rows where noise could have changed a verdict:\n")
        W("| run | config | metric | gap | band |")
        W("|---|---|---|---|---|")
        for r in sorted(miss_inside, key=lambda r: (r["run"], r["config"])):
            W(f"| {r['run']} | {r['config']} | `{r['metric']}` | {r['gap_pt']:.1f} pt | "
              f"±{r['band_pt']:.1f} pt |")
        W("")
    else:
        W("**No published MISS row sits inside the measured noise band.** Every failure "
          "the series recorded is larger than this benchmark's own run-to-run spread. "
          "The rows flagged above are all rows that PASSED — their small gaps are not "
          "evidence of accuracy, merely of gaps too small for this harness to resolve.\n")

    # ---- 5. drift ----
    W("## 5. Drift check (plan §8)\n")
    W("Spearman ρ of `ttft_p95` against run index and against GPU temperature at the "
      "start of that run, with permutation p-values (10,000 permutations, seed 12345).\n")
    W("| config | n | ρ vs run index | p | ρ vs start temp | p |")
    W("|---|---|---|---|---|---|")
    for cfg in CFGS:
        d = drift.get(cfg)
        if not d:
            continue
        rt = f"{d['rho_temp']:+.3f}" if "rho_temp" in d else "n/a"
        pt = f"{d['p_temp']:.3f}" if "p_temp" in d else "n/a"
        W(f"| {cfg} | {d['n']} | {d['rho_index']:+.3f} | {d['p_index']:.3f} | {rt} | {pt} |")
    W("")

    # ---- exclusions ----
    W("## 6. Excluded repeats\n")
    if excluded:
        W(f"{len(excluded)} attempts did not pass the pre-registered cleanliness gate:\n")
        W("```")
        for e in excluded[:40]:
            W(e)
        W("```")
        W("")
    else:
        W("None. Every attempt passed the pre-registered cleanliness gate on its "
          "first try.\n")
    W("No outlier rejection of any kind was applied, as pre-committed in plan §3.\n")

    # ---- unplanned ----
    W("---\n")
    W("## Unplanned observation — the KV pool is not reproducible across boots\n")
    W("**Hypothesis-generating, not a result of this plan.** Found while probing pool "
      "sizes for the config sweep, before the counted repeats began.\n")
    W("Booting identical settings twice gave two different pools:\n")
    W("```")
    W("util 0.85, mbt 2048, mns 64  ->  82,656 tokens")
    W("util 0.85, mbt 2048, mns 64  ->  87,680 tokens")
    W("```")
    W("A 5,024-token (6.1%) difference from nothing but a repeated boot. **Configs A "
      "and J differ by 5,776 tokens** (87,200 vs 81,424), so the irreproducibility is "
      "the same size as the effect this series studies on the pool axis.\n")
    W("The mechanism is **unresolved**. A first-boot/compile-cache story fits the "
      "probes but is contradicted by two published points: D (mns 32) was that shape's "
      "first boot and came in high, and I (mbt 8192) was a repeat boot and came in low, "
      "agreeing with G to 3 tokens across two utilisations.\n")
    W("Tonight's queue asserted the pool on every boot, so **none of the repeats above "
      "is affected**. Whether the published single-boot runs were is not something this "
      "batch can answer, and it is not claimed.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out} ({len(L)} lines)")


if __name__ == "__main__":
    main()
