"""Held-out trace M for run 10, per the README's run-10 protocol.

Three prompt sizes (500 / 1500 / 3000 words), equal counts, bursts of 8, 64 requests
(one third of the canonical 192). 64 is not divisible by 3, so counts are 22/21/21,
assigned round-robin so every burst of 8 mixes all three sizes.

Burst geometry follows workload.py's --bursty convention: Poisson-spaced bursts, with
arrivals inside a burst separated by uniform(0.01, 0.05) s.

The shared prefix is lifted verbatim from results/trace.jsonl so it is the same text,
and therefore the same cache blocks, as the rest of the series. Prompts shorter than
the 1,200-word shared prefix are a truncation of it, as in the burst probe.
"""
import argparse, json, random, sys, os
sys.path.insert(0, os.getcwd())
from replay_sim.workload import VOCAB

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="results/trace.jsonl")
ap.add_argument("--out", default="results/trace_M.jsonl")
ap.add_argument("--n", type=int, default=64)
ap.add_argument("--burst", type=int, default=8)
ap.add_argument("--sizes", type=int, nargs="+", default=[500, 1500, 3000])
ap.add_argument("--sys-len", type=int, default=1200)
ap.add_argument("--out-mean", type=int, default=180)
ap.add_argument("--rate", type=float, default=1.2)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

base = json.loads(open(a.base).readline())
shared = base["prompt"].split()[:a.sys_len]
assert len(shared) == a.sys_len
rng = random.Random(a.seed)

# round-robin sizes -> counts as equal as 64/3 allows
sizes = [a.sizes[i % len(a.sizes)] for i in range(a.n)]

rows, t, in_burst = [], 0.0, 0
for i in range(a.n):
    if in_burst == 0:
        t += rng.expovariate(a.rate / a.burst)     # gap between bursts
        in_burst = a.burst
    else:
        t += rng.uniform(0.01, 0.05)               # near-simultaneous inside a burst
    in_burst -= 1
    target = sizes[i]
    if target <= a.sys_len:
        pw = shared[:target]
    else:
        pw = shared + [VOCAB[rng.randrange(len(VOCAB))] for _ in range(target - a.sys_len)]
    rows.append({"req_id": i, "session": i, "turn": 0, "arrival_s": round(t, 3),
                 "prompt": " ".join(pw), "prompt_len": len(pw),
                 "output_len": max(8, int(rng.gauss(a.out_mean, a.out_mean * 0.3)))})

with open(a.out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

from collections import Counter
c = Counter(r["prompt_len"] for r in rows)
print(f"{a.out}: {len(rows)} requests, span {rows[-1]['arrival_s']:.1f}s")
print(f"  prompt sizes: {dict(sorted(c.items()))}")
gaps = [rows[i]["arrival_s"] - rows[i-1]["arrival_s"] for i in range(1, len(rows))]
print(f"  intra-burst gaps (<=50ms): {sum(1 for g in gaps if g <= 0.051)} of {len(gaps)}"
      f"  -> {len(gaps) - sum(1 for g in gaps if g <= 0.051) + 1} bursts")
