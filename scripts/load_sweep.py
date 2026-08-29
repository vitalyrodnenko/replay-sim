"""TASK 4: provisional load sweep. util x mns x mbt x speedup, all through the
unmodified v0.7 simulator on run-5 perf.json.

Per speedup, config A at THAT SAME speedup is the SLO anchor: a config survives a
speedup if its predicted e2e_p95 <= 1.10 x config A's predicted e2e_p95 at the same
speedup. Each config's capacity is the highest speedup it survives.
"""
import argparse, itertools, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pool_model import predict, build

UTILS = [0.70, 0.75, 0.78, 0.82, 0.85, 0.88]
MNS = [64, 128]
MBT = [2048, 8192]
SPEEDS = [("s1", 1.0, "results/trace.jsonl"), ("s15", 1.5, "results/trace_s15.jsonl"),
          ("s2", 2.0, "results/trace_s2.jsonl"), ("s3", 3.0, "results/trace_s3.jsonl"),
          ("s4", 4.0, "results/trace_s4.jsonl")]
SLO_FACTOR = 1.10
OUTDIR = "results/loadsweep"
BASE = (0.85, 128, 2048)


def tag(u, s, b, sp):
    return f"u{u:.2f}_s{s}_b{b}_{sp}"


def run_one(job):
    u, s, b, blocks, sp, trace = job
    t = tag(u, s, b, sp)
    out = os.path.join(OUTDIR, f"sim_{t}.json")
    cmd = [sys.executable, "-m", "replay_sim.simulator", "--trace", trace,
           "--perf", "results/perf.json", "--num-blocks", str(blocks),
           "--max-num-seqs", str(s), "--max-batched-tokens", str(b),
           "--drop-first", "10", "--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"tag": t, "util": u, "mns": s, "mbt": b, "speed": sp,
                "num_blocks": blocks, "error": r.stderr[-300:]}
    d = json.load(open(out))
    d.update({"tag": t, "util": u, "mns": s, "mbt": b, "speed": sp, "num_blocks": blocks})
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="results/loadsweep/loadsweep.json")
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    pm = build("measured")
    jobs = []
    for u, s, b in itertools.product(UTILS, MNS, MBT):
        blocks = int(predict(pm, u, b, s) // pm["block_size"])
        for sp, _, trace in SPEEDS:
            jobs.append((u, s, b, blocks, sp, trace))
    print(f"{len(jobs)} sims ({len(UTILS)}x{len(MNS)}x{len(MBT)} configs x {len(SPEEDS)} speedups)")
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            rows.append(f.result())
    errs = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]
    if errs:
        print(f"WARNING {len(errs)} sims failed")

    by = {(r["util"], r["mns"], r["mbt"], r["speed"]): r for r in rows}
    speeds = {sp: mult for sp, mult, _ in SPEEDS}
    anchors = {sp: by[(BASE[0], BASE[1], BASE[2], sp)]["e2e_p95_s"] for sp, _, _ in SPEEDS}
    guards = {sp: SLO_FACTOR * anchors[sp] for sp in anchors}

    caps = []
    for u, s, b in itertools.product(UTILS, MNS, MBT):
        surv, detail = 0.0, {}
        for sp, mult, _ in SPEEDS:
            r = by.get((u, s, b, sp))
            ok = r is not None and r["e2e_p95_s"] <= guards[sp]
            detail[sp] = {"e2e_p95": r["e2e_p95_s"] if r else None,
                          "guard": guards[sp], "ok": ok,
                          "gpu_s": r["gpu_s_per_1k_out_tok"] if r else None}
            if ok:
                surv = max(surv, mult)
        at = next((sp for sp, mult, _ in SPEEDS if mult == surv), "s1")
        caps.append({"util": u, "mns": s, "mbt": b,
                     "num_blocks": by[(u, s, b, "s1")]["num_blocks"],
                     "max_speedup": surv,
                     "gpu_s_at_cap": detail[at]["gpu_s"] if surv else None,
                     "is_default": (u, s, b) == BASE, "detail": detail})
    caps.sort(key=lambda c: (-c["max_speedup"], c["gpu_s_at_cap"] if c["gpu_s_at_cap"] else 9e9))
    for i, c in enumerate(caps, 1):
        c["rank"] = i
    json.dump({"caps": caps, "anchors": anchors, "guards": guards,
               "slo_factor": SLO_FACTOR, "n": len(rows), "errors": errs},
              open(a.out, "w"), indent=2)
    d = next(c for c in caps if c["is_default"])
    print(f"default (util 0.85/128/2048): max speedup {d['max_speedup']}x, rank {d['rank']} of {len(caps)}")
    print(f"best: util {caps[0]['util']} mns {caps[0]['mns']} mbt {caps[0]['mbt']} "
          f"-> {caps[0]['max_speedup']}x")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
