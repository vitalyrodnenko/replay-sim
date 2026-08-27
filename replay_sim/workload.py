"""Generate an agentic-style request trace.

Structure mimics agent workloads: S sessions, each session shares a long
system/tool prompt (prefix reuse target) and grows its history across turns.
Prompts are deterministic token-id sequences so the same trace replays
identically in the simulator and against a real vLLM server.

Output: JSONL, one request per line:
  {"req_id", "session", "turn", "arrival_s", "prompt_len", "output_len",
   "prefix_key": [block-content hashes precomputed at block_size granularity]}

For the real vLLM run we also emit prompt text built from a fixed vocabulary
(one word per token, approximately) so tokenized lengths are stable.
"""
import argparse, hashlib, json, random

VOCAB = [f"tok{i}" for i in range(512)]

def words(rng, n):
    return [VOCAB[rng.randrange(len(VOCAB))] for _ in range(n)]

def gen(seed, sessions, turns, sys_len, turn_user, turn_growth, out_mean, rate):
    rng = random.Random(seed)
    reqs = []
    t = 0.0
    # shared corporate system prompt across ALL sessions (strong reuse signal)
    shared_sys = words(rng, sys_len)
    per_session = {}
    for s in range(sessions):
        # per-session tool preamble, reused across that session's turns
        per_session[s] = words(rng, sys_len // 2)
    # interleave turns across sessions with Poisson arrivals
    order = [(s, k) for s in range(sessions) for k in range(turns)]
    rng.shuffle(order)
    order.sort(key=lambda x: x[1])  # turns roughly in order, sessions interleaved
    histories = {s: [] for s in range(sessions)}
    rid = 0
    for (s, k) in order:
        t += rng.expovariate(rate)
        user = words(rng, turn_user + k * turn_growth)
        prompt_words = shared_sys + per_session[s] + histories[s] + user
        out_len = max(8, int(rng.gauss(out_mean, out_mean * 0.3)))
        reqs.append({
            "req_id": rid, "session": s, "turn": k, "arrival_s": round(t, 3),
            "prompt": " ".join(prompt_words),
            "prompt_len": len(prompt_words),
            "output_len": out_len,
        })
        # assistant reply enters history as synthetic words (deterministic)
        histories[s] = histories[s] + user + words(rng, out_len)
        rid += 1
    return reqs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="trace.jsonl")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sessions", type=int, default=24)
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--sys-len", type=int, default=1200)
    ap.add_argument("--turn-user", type=int, default=120)
    ap.add_argument("--turn-growth", type=int, default=20)
    ap.add_argument("--out-mean", type=int, default=180)
    ap.add_argument("--rate", type=float, default=1.2, help="arrivals per second")
    a = ap.parse_args()
    reqs = gen(a.seed, a.sessions, a.turns, a.sys_len, a.turn_user,
               a.turn_growth, a.out_mean, a.rate)
    with open(a.out, "w") as f:
        for r in reqs:
            f.write(json.dumps(r) + "\n")
    tot = sum(r["prompt_len"] for r in reqs)
    print(f"wrote {len(reqs)} requests, {tot} prompt tokens (approx), "
          f"span {reqs[-1]['arrival_s']:.0f}s -> {a.out}")

if __name__ == "__main__":
    main()
