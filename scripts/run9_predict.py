"""Run 9 predictions with v0.8. Frozen predictions are in results/PREDICTIONS_run9.md.

--drop-first 10 everywhere EXCEPT the burst (12 requests) and coldstart (14) traces,
whose real runs were made with no drop because their first arrivals are the subject.
Using 10 there would leave 2 and 4 requests and make sim and real incomparable.
"""
import json, os, random, subprocess, sys
from concurrent.futures import ProcessPoolExecutor, as_completed

OUT = "results/run9"
PERF = "results/perf.json"
CANON = "results/trace.jsonl"

# config -> (blocks, mns, mbt, prefix_caching) from each run's own startup log
CFG = {
    "A": (5450, 128, 2048, True), "B": (5450, 128, 2048, False),
    "C": (2440, 128, 2048, True), "D": (5490, 32, 2048, True),
    "E": (3644, 128, 2048, True), "F": (4607, 128, 2048, True),
    "G": (5141, 128, 8192, True), "H": (5811, 128, 2048, True),
    "I": (4298, 128, 8192, True), "J": (5089, 128, 2048, True),
    "K": (4246, 128, 2048, True),
}


def sim(trace, blocks, mns, mbt, pc, out, drop=10, perreq=None):
    cmd = [sys.executable, "-m", "replay_sim.simulator", "--trace", trace,
           "--perf", PERF, "--num-blocks", str(blocks), "--max-num-seqs", str(mns),
           "--max-batched-tokens", str(mbt), "--drop-first", str(drop), "--out", out]
    if not pc:
        cmd.append("--no-prefix-caching")
    if perreq:
        cmd += ["--per-request", perreq]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"sim failed for {out}:\n{r.stderr[-500:]}")
    return json.load(open(out))


def jitter_trace(src, seed, ms, dst):
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(src)]
    for r in rows:
        r["arrival_s"] = round(max(0.0, r["arrival_s"] + rng.uniform(-ms, ms) / 1000.0), 6)
    with open(dst, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def one_jitter(seed):
    t = f"{OUT}/jitter/trace_J_seed{seed:02d}.jsonl"
    jitter_trace(CANON, seed, 25, t)
    b, mns, mbt, pc = CFG["J"]
    s = sim(t, b, mns, mbt, pc, f"{OUT}/jitter/sim_J_seed{seed:02d}.json")
    return {"seed": seed, "ttft_p95_s": s["ttft_p95_s"], "e2e_p95_s": s["e2e_p95_s"],
            "throughput_tok_s": s["throughput_tok_s"]}


def main():
    os.makedirs(f"{OUT}/jitter", exist_ok=True)
    print("== held-out: config L (config A settings on the bursty trace) ==")
    L = sim("results/trace_bursty.jsonl", 5450, 128, 2048, True,
            f"{OUT}/sim_L.json", 10, f"{OUT}/simpr_L.jsonl")
    print(f"   L: ttft_p95 {L['ttft_p95_s']} e2e_p95 {L['e2e_p95_s']} "
          f"thru {L['throughput_tok_s']} hit {L['prefix_cache_hit_rate']}")

    print("\n== in-sample: A-K on the canonical trace ==")
    for c, (b, mns, mbt, pc) in CFG.items():
        s = sim(CANON, b, mns, mbt, pc, f"{OUT}/sim_{c}.json")
        print(f"   {c}: ttft_p95 {s['ttft_p95_s']:>7.3f}  thru {s['throughput_tok_s']:>6.1f}  "
              f"hit {s['prefix_cache_hit_rate']:.3f}")

    print("\n== in-sample: burst and coldstart (drop-first 0, matching their reals) ==")
    bu = sim("results/trace_burst.jsonl", 5450, 128, 2048, True,
             f"{OUT}/sim_burst.json", 0, f"{OUT}/simpr_burst.jsonl")
    cs = sim("results/trace_coldstart.jsonl", 5450, 128, 2048, True,
             f"{OUT}/sim_coldstart.json", 0, f"{OUT}/simpr_coldstart.jsonl")
    print(f"   burst:     ttft_p95 {bu['ttft_p95_s']}  makespan {bu['makespan_s']}")
    print(f"   coldstart: ttft_p95 {cs['ttft_p95_s']}  makespan {cs['makespan_s']}")

    print("\n== in-sample: 20 jittered J runs, seeds 0-19, +/-25 ms ==")
    res = []
    with ProcessPoolExecutor(max_workers=10) as ex:
        for f in as_completed([ex.submit(one_jitter, s) for s in range(20)]):
            res.append(f.result())
    res.sort(key=lambda r: r["seed"])
    vals = sorted(r["ttft_p95_s"] for r in res)
    print("   ttft_p95 sorted: " + ", ".join(f"{v:.3f}" for v in vals))
    print(f"   min {min(vals):.3f} max {max(vals):.3f} "
          f"spread {100*(max(vals)-min(vals))/min(vals):.1f}% of min")
    json.dump({"jitter": res}, open(f"{OUT}/jitter_J.json", "w"), indent=2)
    print(f"\nwrote {OUT}/")


if __name__ == "__main__":
    main()
