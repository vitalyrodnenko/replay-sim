"""Compare simulator predictions with real runs.

Two levels, because the product claim is about deltas:
  1) absolute error per metric per config
  2) config-change effect: sim-predicted relative change (B vs A, C vs A)
     against the real relative change; the bar is <=15 points of error.

Usage:
  python -m replay_sim.compare \
      --sim sim_A.json sim_B.json sim_C.json \
      --real real_A.json real_B.json real_C.json \
      --labels A B C
"""
import argparse, json

METRICS = ["ttft_p50_s", "ttft_p95_s", "e2e_p50_s", "e2e_p95_s",
           "throughput_tok_s", "prefix_cache_hit_rate"]

def load(p): return json.load(open(p))

def pct(x): return f"{100*x:+.1f}%"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", nargs="+", required=True)
    ap.add_argument("--real", nargs="+", required=True)
    ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--bar", type=float, default=0.15)
    a = ap.parse_args()
    sims = [load(p) for p in a.sim]
    reals = [load(p) for p in a.real]

    print("== ABSOLUTE (sim vs real) ==")
    for lab, s, r in zip(a.labels, sims, reals):
        print(f"-- config {lab}")
        for m in METRICS:
            if s.get(m) is None or r.get(m) is None: continue
            err = (s[m] - r[m]) / r[m] if r[m] else float("nan")
            print(f"   {m:24s} sim={s[m]:>10} real={r[m]:>10}  err={pct(err)}")

    print("\n== CONFIG-CHANGE EFFECT (vs config", a.labels[0], ") ==")
    ok = True
    for i in range(1, len(a.labels)):
        print(f"-- {a.labels[i]} vs {a.labels[0]}")
        for m in METRICS:
            s0, s1 = sims[0].get(m), sims[i].get(m)
            r0, r1 = reals[0].get(m), reals[i].get(m)
            if None in (s0, s1, r0, r1) or 0 in (s0, r0): continue
            ds, dr = s1/s0 - 1, r1/r0 - 1
            gap = abs(ds - dr)
            flag = "OK " if gap <= a.bar else "MISS"
            if gap > a.bar: ok = False
            print(f"   {m:24s} sim {pct(ds):>8}  real {pct(dr):>8}  "
                  f"gap {100*gap:5.1f}pt  {flag}")
    print("\nVERDICT:", "PASS (delta accuracy within bar)" if ok
          else "FAIL (tighten the model, see MISS rows)")

if __name__ == "__main__":
    main()
