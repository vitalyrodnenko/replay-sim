"""TASK 4 deliverable: results/LOADSWEEP_PROVISIONAL.md."""
import argparse, json, re, os

SPEEDS = [("s1", 1.0), ("s15", 1.5), ("s2", 2.0), ("s3", 3.0), ("s4", 4.0)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", default="results/loadsweep/loadsweep.json")
    ap.add_argument("--load-report", default="results/LOAD_REPORT.md")
    ap.add_argument("--out", default="results/LOADSWEEP_PROVISIONAL.md")
    a = ap.parse_args()
    d = json.load(open(a.sweep))
    caps, guards, anchors = d["caps"], d["guards"], d["anchors"]
    dflt = next(c for c in caps if c["is_default"])
    best = caps[0]
    maxsp = max(m for _, m in SPEEDS)
    cens = [c for c in caps if c["max_speedup"] >= maxsp]
    fail1 = [c for c in caps if c["max_speedup"] == 0.0]
    head = 100 * (1 - best["detail"]["s4"]["gpu_s"] / dflt["detail"]["s4"]["gpu_s"])

    answer_yes = None
    if os.path.exists(a.load_report):
        txt = open(a.load_report).read()
        m = re.search(r"safe to drive tonight's load sweep\?\s*\*\*(YES|NO)\*\*", txt)
        if m:
            answer_yes = (m.group(1) == "YES")
        dec = re.search(r"\*\*The number that decides it: ([^*]+)\*\*", txt)
        decnum = dec.group(1) if dec else None
    else:
        decnum = None

    L, W = [], None
    W = L.append
    W("> # PROVISIONAL: valid only if LOAD_REPORT.md answers yes; guard thresholds "
      "must be re-anchored to measured baselines before any external use.\n")
    if answer_yes is False:
        W("> ## ⚠ LOAD_REPORT.md answers **NO**.\n")
        W(f"> The cost model failed its held-out load validation"
          f"{f' — {decnum}' if decnum else ''}. **Every number below is therefore "
          f"unusable as a capacity claim.** It is published because the sweep was "
          f"specified and the grid is worth keeping, not because it can be acted on. "
          f"See §0.\n")
    elif answer_yes:
        W("> LOAD_REPORT.md answers **yes**. The guard thresholds are still simulated "
          "and must be re-anchored to measured baselines before any external use.\n")
    W("\n# LOADSWEEP_PROVISIONAL — capacity ranking on the cost model\n")
    W("**Date:** 2026-08-29  ")
    W("**No simulator, `perf.json`, or verdict change.** Simulated throughout: "
      "no config below was run for real at any speedup.\n")

    W("## 0. Why this is not actionable\n")
    if answer_yes is False:
        W(f"`LOAD_REPORT.md` put the same simulator against real runs at 1.5×, 2× and "
          f"3× and it failed the pre-registered rule: {decnum or 'a cost row missed the bar'}. "
          f"Worse for this document specifically, it failed **in the optimistic "
          f"direction** — at 3× the model predicted throughput rising +113.6% where the "
          f"server delivered +98.2%, so it under-models saturation. A capacity table "
          f"built on it will overstate how much load each config survives, which is "
          f"exactly the error that matters here.\n")
        W("The validated range is **up to 2×**, where every cost row passed with gaps "
          "of 0.7 points or less. Rows at 3× and 4× below are extrapolation past the "
          "point where the model is known to break.\n")
    W("A second, independent reason: the SLO guard is `1.10 ×` config A's **predicted** "
      "`e2e_p95` at the same speedup. Predicted `e2e_p95` ran 3–15% below measured on "
      "every real run in `LOAD_REPORT.md`, so these guards sit below the real ones and "
      "admit configs a measured guard would reject.\n")

    W("## 1. Method\n")
    W(f"util {{0.70, 0.75, 0.78, 0.82, 0.85, 0.88}} × mns {{64, 128}} × mbt "
      f"{{2048, 8192}}, prefix caching on = 24 configs, each simulated at speedups "
      f"{{1, 1.5, 2, 3, 4}} via the scaled traces = **{d['n']} sims**, v0.7 + run-5 "
      f"`perf.json`, `--drop-first 10`.\n")
    W("A config **survives** a speedup if its predicted `e2e_p95` at that speedup is "
      "within 1.10× of config A's predicted `e2e_p95` **at the same speedup** — the "
      "anchor moves with the load, so this measures relative resilience, not absolute "
      "latency.\n")
    W("| speedup | config-A anchor `e2e_p95` | guard (1.10×) |")
    W("|---|---|---|")
    for sp, mult in SPEEDS:
        W(f"| {mult:g}× | {anchors[sp]:.3f} s | {guards[sp]:.3f} s |")
    W("")

    W("## 2. Capacity table\n")
    W("| rank | util | mns | mbt | blocks | max survivable speedup | `gpu_s_per_1k` at cap |")
    W("|---|---|---|---|---|---|---|")
    for c in caps:
        mark = " ← **default (A)**" if c["is_default"] else ""
        cap = f"**≥{c['max_speedup']:g}×**" if c["max_speedup"] >= maxsp else (
              f"{c['max_speedup']:g}×" if c["max_speedup"] else "**fails at 1×**")
        g = f"{c['gpu_s_at_cap']:.3f}" if c["gpu_s_at_cap"] else "—"
        W(f"| {c['rank']} | {c['util']:.2f} | {c['mns']} | {c['mbt']} | "
          f"{c['num_blocks']:,} | {cap} | {g}{mark} |")
    W("")

    W("## 3. What the table does and does not say\n")
    W(f"**The capacity metric is right-censored.** {len(cens)} of {len(caps)} configs "
      f"survive {maxsp:g}×, the largest speedup tested, so their true capacity is "
      f"`≥{maxsp:g}×` and unknown. The ranking among them is decided entirely by the "
      f"tie-break — `gpu_s_per_1k` at {maxsp:g}× — not by capacity at all. Extending "
      f"the axis past 4× would be needed to separate them, and per §0 that is well "
      f"beyond where the model is trustworthy.\n")
    W(f"**{len(fail1)} configs fail at 1×**, all of them util 0.70, or util 0.75 with "
      f"mbt 8192. Their predicted `e2e_p95` at baseline load is 11–22 s against a "
      f"7.47 s guard: the pool is small enough that eviction dominates before any extra "
      f"load is applied.\n")
    W(f"**The default's position: rank {dflt['rank']} of {len(caps)}**, surviving "
      f"`≥{dflt['max_speedup']:g}×` with `gpu_s_per_1k` = "
      f"{dflt['detail']['s4']['gpu_s']:.3f} at 4×.\n")
    W(f"**Best config's headroom over the default: {head:.2f}%** — util "
      f"{best['util']:.2f}, mns {best['mns']}, mbt {best['mbt']} at "
      f"{best['detail']['s4']['gpu_s']:.3f} vs {dflt['detail']['s4']['gpu_s']:.3f} "
      f"`gpu_s_per_1k` at 4×, both censored at the same survivable speedup. That "
      f"{head:.2f}% is a difference between two simulated numbers from a model that "
      f"just failed its load validation; it is not a saving anyone should plan against.\n")

    W("## 4. Was Task 1 cut short?\n")
    W("No. All three scaled traces were predicted, frozen, committed and run for real "
      "with the full protocol, and every boot asserted the 87,200-token pool. The "
      "session finished measurement well inside its budget. The `no` in "
      "`LOAD_REPORT.md` is a result, not a truncation.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out} (load_report_yes={answer_yes}, headroom {head:.2f}%)")


if __name__ == "__main__":
    main()
