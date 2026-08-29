"""TASK 2: a 12-request burst, all arriving at t=0, alternating short and long
prompts over the same shared prefix.

NOTE ON A CONFLICT IN THE SPEC. The brief asks for ~700-token short prompts and a
shared 1,200-word prefix. A 700-token prompt cannot contain a 1,200-token prefix.
Resolved as: the short prompts are 700 tokens that share the FIRST 700 words of the
common prefix, and the long prompts are 2,600 tokens = the full 1,200-word shared
prefix + 1,400 unique words. Every request therefore still shares a real prefix with
every other; the short ones just share less of it. Recorded here and in the report.

The shared prefix is lifted verbatim from results/trace.jsonl so it is the same text,
and therefore the same cache blocks, the rest of the series uses.
"""
import argparse, json, random, sys, os
sys.path.insert(0, os.getcwd())
from replay_sim.workload import VOCAB

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="results/trace.jsonl")
ap.add_argument("--out", default="results/trace_burst.jsonl")
ap.add_argument("--n", type=int, default=12)
ap.add_argument("--short", type=int, default=700)
ap.add_argument("--long", type=int, default=2600)
ap.add_argument("--sys-len", type=int, default=1200)
ap.add_argument("--out-len", type=int, default=128)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

base = json.loads(open(a.base).readline())
shared = base["prompt"].split()[:a.sys_len]
assert len(shared) == a.sys_len, f"base trace prefix shorter than {a.sys_len}"

rng = random.Random(a.seed)
rows = []
for i in range(a.n):
    is_short = (i % 2 == 0)
    target = a.short if is_short else a.long
    if target <= a.sys_len:
        pw = shared[:target]                      # pure prefix truncation
    else:
        pw = shared + [VOCAB[rng.randrange(len(VOCAB))] for _ in range(target - a.sys_len)]
    rows.append({"req_id": i, "session": i, "turn": 0, "arrival_s": 0.0,
                 "prompt": " ".join(pw), "prompt_len": len(pw),
                 "output_len": a.out_len})

with open(a.out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")

shorts = [r for r in rows if r["prompt_len"] == a.short]
longs = [r for r in rows if r["prompt_len"] == a.long]
print(f"{a.out}: {len(rows)} requests, all arrival_s=0.0")
print(f"  short: {len(shorts)} x {a.short} tok (rids {[r['req_id'] for r in shorts]})")
print(f"  long : {len(longs)} x {a.long} tok (rids {[r['req_id'] for r in longs]})")
print(f"  every request shares the first {min(a.short, a.sys_len)} words; "
      f"the long ones share all {a.sys_len}")
