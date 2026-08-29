"""Scale a trace's arrival times by a constant divisor.

Prompts, rids, output lengths and order are untouched: only arrival_s changes,
so the simulator and bench.py read identical files and the load axis is the
only thing that moves.

usage: python scripts/scale_trace.py --in results/trace.jsonl --div 1.5 --out results/trace_s15.jsonl
"""
import argparse, json

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp", required=True)
ap.add_argument("--div", type=float, required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

rows = [json.loads(l) for l in open(a.inp)]
with open(a.out, "w") as f:
    for r in rows:
        r["arrival_s"] = round(r["arrival_s"] / a.div, 6)
        f.write(json.dumps(r) + "\n")
span = max(r["arrival_s"] for r in rows)
print(f"{a.out}: {len(rows)} requests, arrival span 0..{span:.2f}s (divisor {a.div})")
