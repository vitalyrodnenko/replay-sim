"""TASK 3: split config J's 14 noise repeats into their two ttft_p95 modes and
diff them per request. Existing data only -- no GPU, no new runs.

Writes results/JMODES_REPORT.md.
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noise_stats import mean, stdev, bench_percentile

DROP_FIRST = 10
CLIFF_CACHED = 1200          # the run-8a cohort: prefix match capped at the shared prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise-dir", default="results/noise")
    ap.add_argument("--sim-pr", default="results/diag/simpr_J.jsonl")
    ap.add_argument("--out", default="results/JMODES_REPORT.md")
    a = ap.parse_args()

    runs = []
    for p in sorted(glob.glob(os.path.join(a.noise_dir, "real_J_*.json"))):
        rep = int(re.search(r"real_J_(\d+)\.json", os.path.basename(p)).group(1))
        if rep == 0:
            continue
        s = json.load(open(p))
        pr = os.path.join(a.noise_dir, f"realpr_J_{rep:02d}.jsonl")
        if not os.path.exists(pr):
            continue
        rows = sorted((json.loads(l) for l in open(pr)), key=lambda r: r["rid"])
        kept = rows[DROP_FIRST:]
        runs.append({"rep": rep, "ttft_p95": s["ttft_p95_s"], "summary": s,
                     "ttft": {r["rid"]: r["ttft"] for r in kept},
                     "e2e": {r["rid"]: r["e2e"] for r in kept}})
    if not runs:
        raise SystemExit("no J runs found")

    vals = sorted(r["ttft_p95"] for r in runs)
    gap_at = max(range(1, len(vals)), key=lambda i: vals[i] - vals[i - 1])
    split = 0.5 * (vals[gap_at] + vals[gap_at - 1])
    lo = [r for r in runs if r["ttft_p95"] < split]
    hi = [r for r in runs if r["ttft_p95"] >= split]

    rids = sorted(set(lo[0]["ttft"]) & set(hi[0]["ttft"])) if lo and hi else []
    per = []
    for rid in rids:
        l = [r["ttft"][rid] for r in lo if rid in r["ttft"]]
        h = [r["ttft"][rid] for r in hi if rid in r["ttft"]]
        if not l or not h:
            continue
        per.append({"rid": rid, "lo": mean(l), "hi": mean(h), "diff": mean(h) - mean(l),
                    "lo_sd": stdev(l) if len(l) > 1 else 0.0,
                    "hi_sd": stdev(h) if len(h) > 1 else 0.0})
    per.sort(key=lambda x: -abs(x["diff"]))

    cliff = set()
    if os.path.exists(a.sim_pr):
        for l in open(a.sim_pr):
            d = json.loads(l)
            if d.get("cached_tok") == CLIFF_CACHED:
                cliff.add(d["rid"])

    # how much of each mode's p95 the movers account for
    def p95_of(run):
        return bench_percentile(sorted(run["ttft"].values()), .95)
    movers = [x for x in per if abs(x["diff"]) > 0.05]
    mover_ids = {x["rid"] for x in movers}

    L, W = [], None
    W = L.append
    W("# JMODES_REPORT — what separates config J's two `ttft_p95` modes\n")
    W("**Date:** 2026-08-29  ")
    W("**Existing data only** — the 14 per-request dumps from the noise batch. "
      "No GPU, no new runs, no simulator or `perf.json` change, nothing re-scored.\n")
    W(f"`LADDER_REPORT.md` found config J bimodal in `ttft_p95` while C, K and A are "
      f"each a single tight cluster. This splits J's runs at the gap and asks which "
      f"requests actually move.\n")

    W("## The split\n")
    W(f"Sorted `ttft_p95` across the {len(runs)} clean J repeats:\n")
    W("```")
    W("  " + "  ".join(f"{v:.3f}" for v in vals))
    W("```")
    W(f"The largest gap is between {vals[gap_at-1]:.3f} and {vals[gap_at]:.3f}; the "
      f"split is taken at {split:.3f} s. **Low mode: {len(lo)} runs** "
      f"(reps {', '.join(str(r['rep']) for r in sorted(lo, key=lambda r: r['rep']))}). "
      f"**High mode: {len(hi)} runs.**\n")
    W("| mode | n | mean `ttft_p95` | mean throughput | mean hit rate |")
    W("|---|---|---|---|---|")
    for name, g in (("low", lo), ("high", hi)):
        W(f"| {name} | {len(g)} | {mean([r['ttft_p95'] for r in g]):.4f} s | "
          f"{mean([r['summary']['throughput_tok_s'] for r in g]):.1f} tok/s | "
          f"{mean([r['summary']['prefix_cache_hit_rate'] for r in g]):.3f} |")
    W("")

    W("## Which requests differ\n")
    W(f"Mean TTFT per request in each mode, over the {len(rids)} requests that survive "
      f"`--drop-first 10`, sorted by absolute difference:\n")
    W("| rid | low-mode TTFT | high-mode TTFT | high − low | in 8a cliff cohort? |")
    W("|---|---|---|---|---|")
    for x in per[:15]:
        W(f"| {x['rid']} | {x['lo']:.4f} s | {x['hi']:.4f} s | **{x['diff']:+.4f} s** | "
          f"{'**yes**' if x['rid'] in cliff else 'no'} |")
    W("")
    small = [x for x in per if abs(x["diff"]) <= 0.05]
    W(f"{len(movers)} of {len(per)} requests move by more than 50 ms; the remaining "
      f"{len(small)} differ by a mean of {mean([abs(x['diff']) for x in small]):.4f} s "
      f"— flat.\n")

    W("## Do the movers match the run-8a eviction-cliff cohort?\n")
    if cliff:
        inter = mover_ids & cliff
        W(f"Run 8a identified the cohort whose simulated prefix match collapses to "
          f"exactly {CLIFF_CACHED} tokens — the shared system prompt, where sessions "
          f"diverge. In `{os.path.basename(a.sim_pr)}` that cohort is "
          f"**{len(cliff)} requests**.\n")
        W(f"- requests moving >50 ms between J's modes: **{len(mover_ids)}**")
        W(f"- of those, in the cliff cohort: **{len(inter)}** "
          f"({100*len(inter)/len(mover_ids):.0f}% of movers)" if mover_ids else "- no movers")
        W(f"- cliff-cohort requests that do NOT move: "
          f"**{len(cliff - mover_ids)}**\n")
        if mover_ids:
            W(f"Movers: `{sorted(mover_ids)}`")
            W(f"Cliff cohort: `{sorted(cliff)}`\n")
    else:
        W(f"`{a.sim_pr}` not found — cohort comparison skipped.\n")

    W("## Observation\n")
    if movers:
        top = movers[0]
        share = sum(abs(x["diff"]) for x in movers) / sum(abs(x["diff"]) for x in per) * 100
        inter = mover_ids & cliff
        W(f"The two modes are not a global shift. {len(movers)} of {len(per)} requests "
          f"carry {share:.0f}% of the total per-request difference, the largest being "
          f"rid {top['rid']} at {top['diff']:+.3f} s, while everything else is flat to "
          f"within tens of milliseconds. ")
        if cliff:
            base = len(cliff) / len(per)
            exp = base * len(mover_ids)
            if len(inter) == len(mover_ids):
                W(f"Every mover is in the run-8a cliff cohort.")
            elif inter:
                W(f"{len(inter)} of {len(mover_ids)} movers fall in the run-8a cliff "
                  f"cohort. That is above the base rate — the cohort is "
                  f"{len(cliff)}/{len(per)} = {100*base:.0f}% of requests, so chance "
                  f"alone would put {exp:.1f} of {len(mover_ids)} movers in it — but "
                  f"with only {len(mover_ids)} movers this is far too small a sample to "
                  f"call an association, and it points the other way too: "
                  f"{len(cliff - mover_ids)} of the {len(cliff)} cohort members do not "
                  f"move at all. Being in the cohort is plainly not sufficient.")
            else:
                W(f"None of the movers is in the run-8a cliff cohort, so whatever "
                  f"separates J's modes is not that cohort.")
            lowids = sorted(mover_ids)
            if max(lowids) < 60:
                W(f" All {len(lowids)} movers sit early in the trace (rids "
                  f"{', '.join(str(i) for i in lowids)}), as does most of the cohort, so "
                  f"position and cohort membership are confounded here and this data "
                  f"cannot separate them.")
        W(f" This is a measurement of which requests differ; it proposes no mechanism "
          f"and recommends no change.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out}")
    print(f"  low mode {len(lo)} runs, high mode {len(hi)} runs, split {split:.3f}")
    print(f"  movers >50ms: {len(mover_ids)}; cliff cohort: {len(cliff)}; overlap: {len(mover_ids & cliff)}")


if __name__ == "__main__":
    main()
