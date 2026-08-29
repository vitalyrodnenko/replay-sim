"""SWEEP2: capacity inside the validated <=2x envelope. Implements SWEEP2_PLAN.md.

Guard = 1.10 x the MEASURED config-A e2e_p95 at the same speedup.
v0.7 simulator + run-5 perf.json, both untouched. Writes no perf.json.
"""
import argparse, itertools, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pool_model import predict, build

UTILS = [0.70, 0.75, 0.78, 0.82, 0.85, 0.88]
MNS = [64, 128]
MBT = [2048, 8192]
SPEEDS = [("s1", 1.0, "results/trace.jsonl"),
          ("s15", 1.5, "results/trace_s15.jsonl"),
          ("s2", 2.0, "results/trace_s2.jsonl")]
ANCHOR_BRIEFED = {"s1": 7.793, "s15": 11.625, "s2": 24.900}
ANCHOR_SENS = {"s1": 7.543, "s15": 11.625, "s2": 24.900}
SLO = 1.10
BASE = (0.85, 128, 2048)
OUTDIR = "results/sweep2"


def run_one(job):
    u, s, b, blocks, sp, trace = job
    tag = f"u{u:.2f}_s{s}_b{b}_{sp}"
    out = os.path.join(OUTDIR, f"sim_{tag}.json")
    cmd = [sys.executable, "-m", "replay_sim.simulator", "--trace", trace,
           "--perf", "results/perf.json", "--num-blocks", str(blocks),
           "--max-num-seqs", str(s), "--max-batched-tokens", str(b),
           "--drop-first", "10", "--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"tag": tag, "util": u, "mns": s, "mbt": b, "speed": sp, "error": r.stderr[-300:]}
    d = json.load(open(out))
    d.update({"tag": tag, "util": u, "mns": s, "mbt": b, "speed": sp, "num_blocks": blocks})
    return d


def capacities(by, anchors):
    guards = {sp: SLO * anchors[sp] for sp in anchors}
    caps = []
    for u, s, b in itertools.product(UTILS, MNS, MBT):
        surv, detail = 0.0, {}
        for sp, mult, _ in SPEEDS:
            r = by.get((u, s, b, sp))
            ok = r is not None and r["e2e_p95_s"] <= guards[sp]
            detail[sp] = {"e2e_p95": r["e2e_p95_s"] if r else None, "guard": guards[sp],
                          "ok": ok, "gpu_s": r["gpu_s_per_1k_out_tok"] if r else None}
            if ok:
                surv = max(surv, mult)
        at = next((sp for sp, m, _ in SPEEDS if m == surv), None)
        caps.append({"util": u, "mns": s, "mbt": b,
                     "num_blocks": by[(u, s, b, "s1")]["num_blocks"],
                     "max_speedup": surv,
                     "gpu_s_at_cap": detail[at]["gpu_s"] if at else None,
                     "is_default": (u, s, b) == BASE, "detail": detail})
    caps.sort(key=lambda c: (-c["max_speedup"],
                             c["gpu_s_at_cap"] if c["gpu_s_at_cap"] is not None else 9e9))
    for i, c in enumerate(caps, 1):
        c["rank"] = i
    return caps, guards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default="results/sweep2/sweep2.json")
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    pm = build("measured")
    jobs = []
    for u, s, b in itertools.product(UTILS, MNS, MBT):
        blocks = int(predict(pm, u, b, s) // pm["block_size"])
        for sp, _, trace in SPEEDS:
            jobs.append((u, s, b, blocks, sp, trace))
    print(f"{len(jobs)} sims = {len(UTILS)*len(MNS)*len(MBT)} configs x {len(SPEEDS)} speedups")
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(run_one, j) for j in jobs]):
            rows.append(f.result())
    errs = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]
    by = {(r["util"], r["mns"], r["mbt"], r["speed"]): r for r in rows}

    caps_p, guards_p = capacities(by, ANCHOR_BRIEFED)
    caps_s, guards_s = capacities(by, ANCHOR_SENS)
    sens = {(c["util"], c["mns"], c["mbt"]): c["max_speedup"] for c in caps_s}
    diff = [c for c in caps_p if sens[(c["util"], c["mns"], c["mbt"])] != c["max_speedup"]]

    json.dump({"caps": caps_p, "caps_sensitivity": caps_s, "guards": guards_p,
               "guards_sensitivity": guards_s, "anchors": ANCHOR_BRIEFED,
               "anchors_sensitivity": ANCHOR_SENS, "differ_under_sensitivity": diff,
               "n": len(rows), "errors": errs}, open(a.out, "w"), indent=2)
    d = next(c for c in caps_p if c["is_default"])
    print(f"default rank {d['rank']}/{len(caps_p)}, cap {d['max_speedup']}x")
    print(f"best: util {caps_p[0]['util']} mns {caps_p[0]['mns']} mbt {caps_p[0]['mbt']} "
          f"cap {caps_p[0]['max_speedup']}x gpu_s {caps_p[0]['gpu_s_at_cap']:.3f}")
    print(f"configs whose capacity differs under the 7.543 sensitivity: {len(diff)}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
