"""Render results/SWEEP_REPORT.md from the sweep output(s)."""
import argparse, json

METRIC_COLS = [("gpu_s_per_1k_out_tok", "gpu_s/1k"), ("e2e_p95_s", "e2e_p95"),
               ("ttft_p95_s", "ttft_p95"), ("throughput_tok_s", "tok/s"),
               ("prefix_cache_hit_rate", "hit")]


def cfgstr(r):
    return f"util {r['util']:.2f} · mns {r['mns']:>3} · mbt {r['mbt']:>4} · pc {r['pc']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measured", default="results/sweep/sweep_results.json")
    ap.add_argument("--optimistic", default="results/sweep/sweep_results_optimistic.json")
    ap.add_argument("--out", default="results/SWEEP_REPORT.md")
    a = ap.parse_args()

    d = json.load(open(a.measured))
    base, feas, rows = d["baseline"], d["ranked_feasible"], d["rows"]
    pm = d["pool_model"]
    try:
        alt = json.load(open(a.optimistic))
    except FileNotFoundError:
        alt = None

    L = []
    W = L.append
    W("# SWEEP_REPORT — config sweep on the validated cost model\n")
    W("**Date:** 2026-08-29  ")
    W("**Simulator:** v0.7 as installed in run 7, unmodified. **`perf.json`:** run-5, unmodified.  ")
    W("**Trace:** `results/trace.jsonl`, the same 192 requests every run in the series used.  ")
    W("**No physics change, no calibration change, no verdict.**\n")

    W("## What is being asked\n")
    W("For each of the 256 configurations below, what does the simulator predict it "
      "would cost to serve this workload, and which of them stay inside an SLO guard "
      "derived from the current default?\n")
    W(f"- **Objective:** minimise `gpu_s_per_1k_out_tok`.")
    W(f"- **SLO guard:** predicted `e2e_p95` ≤ {d['slo_factor']:.2f} × config A "
      f"= **{d['slo_guard_s']:.3f} s**.")
    W(f"- **Grid:** util × mns × mbt × prefix-caching = **{d['n_configs']} configs**, "
      f"of which **{d['n_feasible']}** clear the guard.\n")

    W("## How much each number is worth\n")
    W("This matters more than the ranking, so it goes first.\n")
    W("- **The objective is the part the series actually validated.** Across runs 3–7 "
      "every held-out cost row passed: `throughput_tok_s` and `prefix_cache_hit_rate` "
      "gaps never exceeded the 15-point bar on any held-out config. "
      "`gpu_s_per_1k_out_tok` is derived from the same `gpu_busy_s` accounting.")
    W("- **The SLO guard is weaker.** `e2e_p95` carried a mean absolute error near 6% "
      "in-sample. A config sitting within a few percent of the guard could be on "
      "either side of it in reality.")
    W("- **`ttft_p95` is reported but must not be trusted for ranking.** It is the one "
      "metric that has failed on every held-out config since run 3, and run 7 measured "
      "it over-predicting by +52.9% (F), +32.5% (J) and +37.0% (K) in the "
      "pool-pressure zone — exactly where the cheap candidates below sit.")
    W("- **Pool sizes are modelled, and the pool is not boot-reproducible.** Booting "
      "identical settings twice gave 82,656 and 87,680 tokens "
      "(`results/NOISE_PLAN.md`, amendment). Levels marked SINGLE/ESTIMATED below rest "
      "on one boot each.\n")

    W("### Pool model\n")
    W(f"`tokens = base(util) + off_mbt[mbt] + off_mns[mns]`, base fitted on "
      f"{pm['base_points']} reference-shape points (collinear to within 4 tokens).\n")
    W("| axis | level | offset (tokens) | confidence | provenance |")
    W("|---|---|---|---|---|")
    for name, meta in (("mbt", pm["off_mbt_meta"]), ("mns", pm["off_mns_meta"])):
        for k, v in sorted(meta.items(), key=lambda kv: int(kv[0])):
            W(f"| {name} | {k} | {v['tokens']:+,} | {v['confidence']} | {v['provenance']} |")
    W("")

    W("## Top 10 feasible configs\n")
    W("| # | config | blocks | gpu_s/1k | vs A | e2e_p95 | ttft_p95 | tok/s | hit |")
    W("|---|---|---|---|---|---|---|---|---|")
    for r in feas[:10]:
        mark = " ← **default (A)**" if r["is_baseline"] else ""
        W(f"| {r['rank']} | {cfgstr(r)}{mark} | {r['num_blocks']:,} | "
          f"{r['gpu_s_per_1k_out_tok']:.3f} | {r['cost_vs_base_pct']:+.2f}% | "
          f"{r['e2e_p95_s']:.3f} | {r['ttft_p95_s']:.3f} | "
          f"{r['throughput_tok_s']:.1f} | {r['prefix_cache_hit_rate']:.3f} |")
    W("")

    br = d["baseline_rank"]
    W("## Where the default sits\n")
    W(f"Config A — {cfgstr(base)} — ranks **{br} of {d['n_feasible']}** feasible "
      f"configs, at `gpu_s_per_1k_out_tok` = {base['gpu_s_per_1k_out_tok']:.3f}.\n")

    best = feas[0]
    saving = -best["cost_vs_base_pct"]
    W("## Headline\n")
    W(f"> **Predicted cost-per-task saving of the best feasible config over the "
      f"current default: {saving:.2f}%.**\n")
    W(f"Best: {cfgstr(best)} ({best['num_blocks']:,} blocks), "
      f"`gpu_s_per_1k_out_tok` {best['gpu_s_per_1k_out_tok']:.3f} vs "
      f"{base['gpu_s_per_1k_out_tok']:.3f}, with predicted `e2e_p95` "
      f"{best['e2e_p95_s']:.3f} s against a {d['slo_guard_s']:.3f} s guard.\n")

    if alt:
        af = alt["ranked_feasible"]
        W("## Robustness to the pool irreproducibility\n")
        W(f"The whole sweep was re-run with every SINGLE/ESTIMATED pool level raised by "
          f"{pm['irreproducibility_tokens']:,} tokens — the size of the observed "
          f"boot-to-boot spread — to see whether the ranking survives it.\n")
        W(f"- feasible configs: {d['n_feasible']} → {alt['n_feasible']}")
        W(f"- best config: `{best['tag']}` → `{af[0]['tag']}`"
          f"{'  (**unchanged**)' if af[0]['tag'] == best['tag'] else '  (**changed**)'}")
        W(f"- headline saving: {saving:.2f}% → {-af[0]['cost_vs_base_pct']:.2f}%")
        top_m = [r["tag"] for r in feas[:10]]
        top_o = [r["tag"] for r in af[:10]]
        W(f"- top-10 membership overlap: **{len(set(top_m) & set(top_o))}/10**\n")

    W("## Full ranking\n")
    W(f"All {d['n_configs']} configs with their predictions are in "
      f"`results/sweep/sweep_results.json`; each individual simulator output is in "
      f"`results/sweep/sim_<tag>.json`.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out} ({len(L)} lines)")


if __name__ == "__main__":
    main()
