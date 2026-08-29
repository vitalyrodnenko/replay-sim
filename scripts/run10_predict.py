"""Run 10 predictions with v0.9. Frozen predictions: results/PREDICTIONS_run10.md.

--dispatch-gap 0.0001 (the Step-0 measured median) on the burst family: trace_burst,
config L (bursty trace) and held-out config M. Smooth traces use 0.
--drop-first 10 everywhere except burst (12 requests) and coldstart (14), whose real
runs were made with no drop.
"""
import json, os, subprocess, sys

OUT = "results/run10"
PERF = "results/perf.json"
CANON = "results/trace.jsonl"
GAP = 0.0001

CFG = {"A": (5450,128,2048,True), "B": (5450,128,2048,False), "C": (2440,128,2048,True),
       "D": (5490,32,2048,True),  "E": (3644,128,2048,True),  "F": (4607,128,2048,True),
       "G": (5141,128,8192,True), "H": (5811,128,2048,True),  "I": (4298,128,8192,True),
       "J": (5089,128,2048,True), "K": (4246,128,2048,True)}


def sim(trace, blocks, mns, mbt, pc, out, drop=10, perreq=None, gap=0.0):
    cmd = [sys.executable, "-m", "replay_sim.simulator", "--trace", trace, "--perf", PERF,
           "--num-blocks", str(blocks), "--max-num-seqs", str(mns),
           "--max-batched-tokens", str(mbt), "--drop-first", str(drop), "--out", out]
    if not pc: cmd.append("--no-prefix-caching")
    if perreq: cmd += ["--per-request", perreq]
    if gap: cmd += ["--dispatch-gap", str(gap)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"sim failed {out}:\n{r.stderr[-400:]}")
    return json.load(open(out))


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== HELD-OUT: config M (burst geometry, dispatch gap applied) ==")
    M = sim("results/trace_M.jsonl", 5450, 128, 2048, True,
            f"{OUT}/sim_M.json", 10, f"{OUT}/simpr_M.jsonl", GAP)
    print(f"   M: ttft_p95 {M['ttft_p95_s']} e2e_p95 {M['e2e_p95_s']} "
          f"thru {M['throughput_tok_s']} hit {M['prefix_cache_hit_rate']}")

    print("\n== in-sample A-K (canonical, gap 0) ==")
    for c,(b,mns,mbt,pc) in CFG.items():
        s = sim(CANON, b, mns, mbt, pc, f"{OUT}/sim_{c}.json")
        print(f"   {c}: ttft_p95 {s['ttft_p95_s']:>8.3f}  thru {s['throughput_tok_s']:>6.1f}  hit {s['prefix_cache_hit_rate']:.3f}")

    print("\n== in-sample L (bursty trace, gap applied) ==")
    Lr = sim("results/trace_bursty.jsonl", 5450, 128, 2048, True,
             f"{OUT}/sim_L.json", 10, f"{OUT}/simpr_L.jsonl", GAP)
    print(f"   L: ttft_p95 {Lr['ttft_p95_s']}  thru {Lr['throughput_tok_s']}  hit {Lr['prefix_cache_hit_rate']}")

    print("\n== in-sample burst (gap applied, drop 0) and coldstart (gap 0, drop 0) ==")
    bu = sim("results/trace_burst.jsonl", 5450,128,2048,True, f"{OUT}/sim_burst.json", 0,
             f"{OUT}/simpr_burst.jsonl", GAP)
    cs = sim("results/trace_coldstart.jsonl", 5450,128,2048,True, f"{OUT}/sim_coldstart.json", 0,
             f"{OUT}/simpr_coldstart.jsonl", 0.0)
    print(f"   burst:     ttft_p95 {bu['ttft_p95_s']}  makespan {bu['makespan_s']}")
    print(f"   coldstart: ttft_p95 {cs['ttft_p95_s']}  makespan {cs['makespan_s']}")
    print(f"\nwrote {OUT}/")


if __name__ == "__main__":
    main()
