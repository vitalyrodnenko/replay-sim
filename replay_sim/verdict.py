"""Score predictions under VERDICT CRITERION v1 and v2.

v1 (runs 1-4): every metric passes on the relative delta gap <= 15 pt.

v2 (adopted between runs 4 and 5, prospective from run 5):
  1. Cost metrics (throughput_tok_s, gpu_s_per_1k_out_tok,
     prefix_cache_hit_rate): unchanged -- relative delta gap <= 15 pt.
  2. Latency metrics (ttft/e2e, p50/p95): a row passes if the relative delta
     gap <= 15 pt OR the absolute prediction error on the target config's
     value is <= 15%.
  3. Every report shows both counts for the full series.

Rule 1 names gpu_s_per_1k_out_tok, but bench.py does not measure it -- the
real figure is derived from nvidia-smi and is an estimate, so it appears in
the product scorecard and not in either count. The scored metric set is
compare.py's, unchanged, so v1 counts here reproduce the published ones.

Usage:
  python -m replay_sim.verdict --sim sim_A.json sim_H.json \\
      --real real_A.json real_H.json --labels A H
"""
import argparse, json

COST = ["throughput_tok_s", "prefix_cache_hit_rate"]
LATENCY = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s"]
METRICS = LATENCY + COST
BAR = 0.15          # relative delta gap, both criteria
ABS_BAR = 0.15      # absolute error, v2 latency escape hatch


def score(sims, reals, labels, bar=BAR, abs_bar=ABS_BAR):
    """Yield one dict per scored row. Row 0's config is the baseline."""
    for i in range(1, len(labels)):
        for m in METRICS:
            s0, s1 = sims[0].get(m), sims[i].get(m)
            r0, r1 = reals[0].get(m), reals[i].get(m)
            if None in (s0, s1, r0, r1) or 0 in (s0, r0, r1):
                continue
            gap = abs((s1 / s0 - 1) - (r1 / r0 - 1))
            abs_err = abs(s1 - r1) / abs(r1)
            v1 = gap <= bar
            v2 = v1 if m in COST else (v1 or abs_err <= abs_bar)
            yield {"config": labels[i], "metric": m, "kind":
                   "cost" if m in COST else "latency",
                   "sim_delta": s1 / s0 - 1, "real_delta": r1 / r0 - 1,
                   "gap": gap, "abs_err": (s1 - r1) / r1,
                   "v1": v1, "v2": v2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", nargs="+", required=True)
    ap.add_argument("--real", nargs="+", required=True)
    ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--bar", type=float, default=BAR)
    ap.add_argument("--abs-bar", type=float, default=ABS_BAR)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    sims = [json.load(open(p)) for p in a.sim]
    reals = [json.load(open(p)) for p in a.real]
    rows = list(score(sims, reals, a.labels, a.bar, a.abs_bar))

    print(f"baseline: config {a.labels[0]}\n")
    print(f"{'cfg':>4} {'metric':>22} {'sim d':>9} {'real d':>9} {'gap pt':>7} "
          f"{'abs err':>8} {'v1':>5} {'v2':>5}")
    for r in rows:
        print(f"{r['config']:>4} {r['metric']:>22} {100*r['sim_delta']:>+8.1f}% "
              f"{100*r['real_delta']:>+8.1f}% {100*r['gap']:>7.1f} "
              f"{100*r['abs_err']:>+7.1f}% "
              f"{'OK' if r['v1'] else 'MISS':>5} {'OK' if r['v2'] else 'MISS':>5}")
    n = len(rows)
    n1 = sum(r["v1"] for r in rows)
    n2 = sum(r["v2"] for r in rows)
    rescued = [r for r in rows if r["v2"] and not r["v1"]]
    print(f"\nv1: {n1} of {n} rows within bar")
    print(f"v2: {n2} of {n} rows within bar")
    if rescued:
        print("rows passing under v2 but not v1 (latency, abs err <= 15%):")
        for r in rescued:
            print(f"    {r['config']} {r['metric']}: gap {100*r['gap']:.1f} pt, "
                  f"abs err {100*r['abs_err']:+.1f}%")
    print(f"\nVERDICT v1: {'PASS' if n1 == n else 'FAIL'}"
          f"   VERDICT v2: {'PASS' if n2 == n else 'FAIL'}")
    if a.json_out:
        json.dump({"rows": rows, "n": n, "v1": n1, "v2": n2},
                  open(a.json_out, "w"), indent=2)


if __name__ == "__main__":
    main()
