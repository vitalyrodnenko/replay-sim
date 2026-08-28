"""Per-request diagnosis of the ttft_p95 residual. No physics, no verdict.

Aligns sim and real per-request dumps by rid and answers:
  1. Are the SAME requests slow in both? (overlap of the top-5% ttft sets)
  2. Where does the error live? Per-request ttft diff, bucketed by
     arrival time, turn (from the trace), and prompt length.
  3. Ten worst offenders each way, with their context: arrival, turn,
     session, prompt_len, cached tokens (sim side), preemptions.

Usage:
  python -m replay_sim.diagnose --trace trace.jsonl \
      --sim-pr simpr_F.jsonl --real-pr realpr_F.jsonl \
      --drop-first 10 --label F
"""
import argparse, json

def load_jsonl(p):
    return {json.loads(l)["rid"]: json.loads(l) for l in open(p)}

def pct_set(d, key, frac=0.05):
    ranked = sorted(d.values(), key=lambda v: -v[key])
    k = max(1, int(len(ranked) * frac))
    return set(v["rid"] for v in ranked[:k]), ranked[:k]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--sim-pr", required=True)
    ap.add_argument("--real-pr", required=True)
    ap.add_argument("--drop-first", type=int, default=0)
    ap.add_argument("--label", default="?")
    a = ap.parse_args()

    trace = {json.loads(l)["req_id"]: json.loads(l) for l in open(a.trace)}
    sim = load_jsonl(a.sim_pr)
    real = load_jsonl(a.real_pr)
    common = sorted(set(sim) & set(real))
    dropped = set(common[:a.drop_first])
    ids = [i for i in common if i not in dropped]
    S = {i: sim[i] for i in ids}
    R = {i: real[i] for i in ids}

    print(f"== diagnose config {a.label}: {len(ids)} aligned requests ==\n")

    # 1. membership of the slow set
    s_top, s_rank = pct_set(S, "ttft")
    r_top, r_rank = pct_set(R, "ttft")
    inter = s_top & r_top
    print(f"top-5% ttft sets: sim {sorted(s_top)}")
    print(f"                  real {sorted(r_top)}")
    print(f"overlap: {len(inter)}/{len(s_top)} "
          f"({'SAME requests, magnitude problem' if len(inter)>=len(s_top)*0.6 else 'DIFFERENT requests, mechanism problem'})\n")

    # 2. where the error lives
    diffs = {i: S[i]["ttft"] - R[i]["ttft"] for i in ids}
    def bucket_report(name, keyf):
        buckets = {}
        for i in ids:
            buckets.setdefault(keyf(i), []).append(diffs[i])
        print(f"-- mean ttft (sim-real), by {name}:")
        for k in sorted(buckets):
            v = buckets[k]
            print(f"   {name}={k}: {sum(v)/len(v):+.3f}s  (n={len(v)})")
        print()
    bucket_report("turn", lambda i: trace[i]["turn"])
    span = max(trace[i]["arrival_s"] for i in ids) or 1
    bucket_report("arrival_quintile",
                  lambda i: int(5 * trace[i]["arrival_s"] / (span + 1e-9)))
    bucket_report("prompt_len_kbucket",
                  lambda i: trace[i]["prompt_len"] // 1000)

    # 3. worst offenders each way
    worst_over = sorted(ids, key=lambda i: -diffs[i])[:10]
    worst_under = sorted(ids, key=lambda i: diffs[i])[:10]
    def row(i):
        t = trace[i]
        return (f"rid={i:4d} turn={t['turn']} sess={t['session']:3d} "
                f"arr={t['arrival_s']:7.1f} plen={t['prompt_len']:5d} "
                f"sim={S[i]['ttft']:7.3f} real={R[i]['ttft']:7.3f} "
                f"diff={diffs[i]:+7.3f} cached={S[i].get('cached_tok',0):5d} "
                f"pre={S[i].get('preempt',0)}")
    print("-- 10 most OVER-predicted (sim slower than real):")
    for i in worst_over: print("   " + row(i))
    print("\n-- 10 most UNDER-predicted (sim faster than real):")
    for i in worst_under: print("   " + row(i))

if __name__ == "__main__":
    main()
