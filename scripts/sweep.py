"""Config sweep on the validated cost model (v0.7 simulator, run-5 perf.json).

Enumerates every combination of
    util  {0.60,0.65,0.70,0.75,0.78,0.82,0.85,0.88}
    mns   {16,32,64,128}
    mbt   {1024,2048,4096,8192}
    prefix caching {on,off}
= 256 configs, sizes each one's KV pool with the fitted pool model
(results/pool_model.json), and runs the UNMODIFIED simulator on each via its
documented CLI.

Objective: minimise gpu_s_per_1k_out_tok subject to
    predicted e2e_p95 <= 1.10 * config-A baseline.

usage: python scripts/sweep.py [--workers 8]
"""
import argparse, itertools, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pool_model import predict  # noqa: E402

UTILS = [0.60, 0.65, 0.70, 0.75, 0.78, 0.82, 0.85, 0.88]
MNS = [16, 32, 64, 128]
MBT = [1024, 2048, 4096, 8192]
PC = ["on", "off"]

BASELINE = (0.85, 128, 2048, "on")   # config A, as scripts/serve.sh defines it
SLO_FACTOR = 1.10
OUTDIR = "results/sweep"


def tag_of(util, mns, mbt, pc):
    return f"u{util:.2f}_s{mns}_b{mbt}_{pc}"


def run_one(job):
    util, mns, mbt, pc, blocks, trace, perf = job
    tag = tag_of(util, mns, mbt, pc)
    out = os.path.join(OUTDIR, f"sim_{tag}.json")
    cmd = [sys.executable, "-m", "replay_sim.simulator",
           "--trace", trace, "--perf", perf,
           "--num-blocks", str(blocks), "--max-num-seqs", str(mns),
           "--max-batched-tokens", str(mbt), "--drop-first", "10", "--out", out]
    if pc == "off":
        cmd.append("--no-prefix-caching")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"tag": tag, "util": util, "mns": mns, "mbt": mbt, "pc": pc,
                "num_blocks": blocks, "error": r.stderr[-400:]}
    d = json.load(open(out))
    d.update({"tag": tag, "util": util, "mns": mns, "mbt": mbt, "pc": pc,
              "num_blocks": blocks})
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--trace", default="results/trace.jsonl")
    ap.add_argument("--perf", default="results/perf.json")
    ap.add_argument("--pool-model", default="results/pool_model.json")
    ap.add_argument("--out", default="results/sweep/sweep_results.json")
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)

    pm = json.load(open(a.pool_model))
    bs = pm["block_size"]

    jobs = []
    for util, mns, mbt, pc in itertools.product(UTILS, MNS, MBT, PC):
        tokens = predict(pm, util, mbt, mns)
        blocks = int(tokens // bs)
        jobs.append((util, mns, mbt, pc, blocks, a.trace, a.perf))
    print(f"{len(jobs)} configs; pool model worst residual "
          f"{pm['worst_resid_pct']:.3f}% over {pm['n_points']} measured points")

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(run_one, j) for j in jobs]
        for f in as_completed(futs):
            rows.append(f.result())
            done += 1
            if done % 32 == 0:
                print(f"  {done}/{len(jobs)}")

    errs = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]
    if errs:
        print(f"WARNING: {len(errs)} configs failed to simulate")
        for e in errs[:5]:
            print("   ", e["tag"], e["error"][:120])

    bu, bs_, bb, bp = BASELINE
    base = next(r for r in rows if r["util"] == bu and r["mns"] == bs_
                and r["mbt"] == bb and r["pc"] == bp)
    slo = SLO_FACTOR * base["e2e_p95_s"]
    print(f"\nbaseline (config A): gpu_s_per_1k={base['gpu_s_per_1k_out_tok']}  "
          f"e2e_p95={base['e2e_p95_s']}s  ->  SLO guard e2e_p95 <= {slo:.3f}s")

    for r in rows:
        r["feasible"] = r["e2e_p95_s"] <= slo
        r["cost_vs_base_pct"] = 100 * (r["gpu_s_per_1k_out_tok"] /
                                       base["gpu_s_per_1k_out_tok"] - 1)
        r["is_baseline"] = (r["tag"] == base["tag"])

    feas = sorted([r for r in rows if r["feasible"]],
                  key=lambda r: (r["gpu_s_per_1k_out_tok"], r["e2e_p95_s"]))
    for i, r in enumerate(feas, 1):
        r["rank"] = i

    print(f"feasible: {len(feas)} of {len(rows)}")
    base_rank = next((r["rank"] for r in feas if r["is_baseline"]), None)
    print(f"config A rank among feasible: {base_rank}")
    if feas:
        b = feas[0]
        print(f"best: {b['tag']}  gpu_s_per_1k={b['gpu_s_per_1k_out_tok']} "
              f"({b['cost_vs_base_pct']:+.2f}% vs A)  e2e_p95={b['e2e_p95_s']}s")

    json.dump({"baseline": base, "slo_guard_s": slo, "slo_factor": SLO_FACTOR,
               "n_configs": len(rows), "n_feasible": len(feas),
               "baseline_rank": base_rank, "rows": rows, "ranked_feasible": feas,
               "pool_model": pm, "errors": errs},
              open(a.out, "w"), indent=2)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
