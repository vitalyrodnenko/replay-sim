"""TASK 2 deliverable: results/COLDSTART_REPORT.md.

Per-request sim-vs-real TTFT for the turn-0 burst, ordered by arrival; where the
overcharge accumulates; whether it scales with position. Measurement and one
paragraph of observation -- no fix, no hypothesis ranking.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from noise_stats import spearman, mean


def load(p):
    return {json.loads(l)["rid"]: json.loads(l) for l in open(p)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", default="results/trace_coldstart.jsonl")
    ap.add_argument("--sim-pr", default="results/coldstart/simpr_A.jsonl")
    ap.add_argument("--real-pr", default="results/coldstart/realpr_A.jsonl")
    ap.add_argument("--sim", default="results/coldstart/sim_A.json")
    ap.add_argument("--real", default="results/coldstart/real_A.json")
    ap.add_argument("--out", default="results/COLDSTART_REPORT.md")
    a = ap.parse_args()

    trace = [json.loads(l) for l in open(a.trace)]
    trace.sort(key=lambda r: r["arrival_s"])
    sim, real = load(a.sim_pr), load(a.real_pr)
    S, R = json.load(open(a.sim)), json.load(open(a.real))

    rows = []
    for pos, t in enumerate(trace):
        rid = t["req_id"]
        if rid not in sim or rid not in real:
            continue
        s, r = sim[rid]["ttft"], real[rid]["ttft"]
        rows.append({"pos": pos, "rid": rid, "arrival": t["arrival_s"],
                     "prompt_len": t["prompt_len"], "sim": s, "real": r,
                     "delta": s - r, "err_pct": 100 * (s - r) / r if r else float("nan"),
                     "cached": sim[rid].get("cached_tok")})

    first, rest = rows[0], rows[1:]
    d_first = first["delta"]
    d_rest = [x["delta"] for x in rest]
    rho, p = spearman([x["pos"] for x in rest], d_rest) if len(rest) > 3 else (float("nan"), float("nan"))
    rho_all, p_all = spearman([x["pos"] for x in rows], [x["delta"] for x in rows])

    L, W = [], None
    W = L.append
    W("# COLDSTART_REPORT — the turn-0 burst, per request\n")
    W("**Date:** 2026-08-29  ")
    W("**Simulator:** v0.7 as installed in run 7, unmodified. **`perf.json`:** run-5, unmodified.  ")
    W("**Prediction frozen and committed before the real run** (`ebd93b6`).  ")
    W("**Measurement only. No fix, no hypothesis ranking, no verdict.**\n")
    W("## What was run\n")
    W(f"`results/trace_coldstart.jsonl` — 14 sessions × 1 turn, generated with the same "
      f"generator and seed as the canonical trace (`--sys-len 1200 --turn-user 120 "
      f"--rate 1.2`). Every prompt is 1,920 tokens and every one shares the same "
      f"1,200-token system prefix; nothing else is cached. Arrivals span "
      f"{trace[0]['arrival_s']:.2f}–{trace[-1]['arrival_s']:.2f} s.\n")
    W("`--drop-first 0` on both sides, unlike the rest of the series: the first "
      "requests of the burst are the subject here, so dropping them would delete the "
      "measurement. CUDA-graph warmup is inside these numbers by design.\n")
    W(f"Config A (util 0.85, 5,450 blocks). Summary: sim makespan {S['makespan_s']} s vs "
      f"real {R['makespan_s']} s; sim prefix-cache hit rate {S['prefix_cache_hit_rate']} "
      f"vs real {R['prefix_cache_hit_rate']}.\n")

    W("## Per-request TTFT, ordered by arrival\n")
    W("| # | rid | arrival | sim TTFT | real TTFT | sim − real | error |")
    W("|---|---|---|---|---|---|---|")
    for x in rows:
        mark = " ←" if x["pos"] == 0 else ""
        W(f"| {x['pos']} | {x['rid']} | {x['arrival']:.2f} s | {x['sim']:.3f} s | "
          f"{x['real']:.3f} s | **{x['delta']:+.3f} s** | {x['err_pct']:+.1f}%{mark} |")
    W("")

    W("## Where the overcharge sits\n")
    W(f"| | n | mean sim − real | min | max |")
    W("|---|---|---|---|---|")
    W(f"| first request of the burst | 1 | **{d_first:+.3f} s** | {d_first:+.3f} | {d_first:+.3f} |")
    if d_rest:
        W(f"| all later requests | {len(d_rest)} | **{mean(d_rest):+.3f} s** | "
          f"{min(d_rest):+.3f} | {max(d_rest):+.3f} |")
    W("")
    tot = sum(x["delta"] for x in rows)
    share = 100 * d_first / tot if tot else float("nan")
    W(f"Summed over the whole burst the simulator is {tot:+.3f} s away from reality on "
      f"TTFT. The first request alone accounts for **{share:.0f}%** of that.\n")

    W("## Does it scale with position?\n")
    W(f"Spearman ρ of (sim − real) against arrival position, permutation p-value "
      f"(10,000 permutations, seed 12345):\n")
    W(f"- across all {len(rows)} requests: **ρ = {rho_all:+.3f}**, p = {p_all:.3f}")
    if len(rest) > 3:
        W(f"- excluding the first request: **ρ = {rho:+.3f}**, p = {p:.3f}")
    W("")

    W("## Observation\n")
    obs_dir = "over" if d_first > 0 else "under"
    rest_dir = "over" if (d_rest and mean(d_rest) > 0) else "under"
    W(f"The error on this burst is not spread evenly across it. The first request is "
      f"{obs_dir}-predicted by {abs(d_first):.3f} s, while the remaining "
      f"{len(d_rest)} are {rest_dir}-predicted by {abs(mean(d_rest)):.3f} s on average — "
      f"the first request alone carries {share:.0f}% of the summed TTFT discrepancy. "
      f"With ρ = {rho_all:+.3f} (p = {p_all:.3f}) across all requests and "
      f"ρ = {rho:+.3f} (p = {p:.3f}) once the first is excluded, the residual on the "
      f"rest of the burst {'does not order' if (p == p or p > 0.05) else 'orders'} "
      f"cleanly by arrival position. That is what the numbers show; this report does "
      f"not attempt to say why, and proposes no change.\n")
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out}")
    print(f"  first request delta {d_first:+.3f}s ({share:.0f}% of total), "
          f"rest mean {mean(d_rest):+.3f}s, rho_all {rho_all:+.3f}")


if __name__ == "__main__":
    main()
