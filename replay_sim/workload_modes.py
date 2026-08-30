"""Contrasting workload generators for H1. New module, additive:
imports the repo's derived single-token VOCAB from workload.py and
emits the same jsonl schema. Modes:

  chat: single-turn, unique prompts, no shared corporate prefix.
        The anti-agent workload: prefix reuse ~0 by construction.
  rag:  long unique document + short shared instruction template +
        short question, short outputs. Prefill-dominated.

Usage:
  python -m replay_sim.workload_modes --mode chat --out chat.jsonl
  python -m replay_sim.workload_modes --mode rag  --out rag.jsonl
"""
import argparse, json, random
from .workload import VOCAB

def words(rng, n):
    return [VOCAB[rng.randrange(len(VOCAB))] for _ in range(n)]

def gen_chat(seed, n_requests, prompt_mean, prompt_sd, out_mean, rate):
    rng = random.Random(seed)
    t, reqs = 0.0, []
    for rid in range(n_requests):
        t += rng.expovariate(rate)
        plen = max(200, int(rng.gauss(prompt_mean, prompt_sd)))
        out = max(8, int(rng.gauss(out_mean, out_mean * 0.3)))
        reqs.append({"req_id": rid, "session": rid, "turn": 0,
                     "arrival_s": round(t, 3),
                     "prompt": " ".join(words(rng, plen)),
                     "prompt_len": plen, "output_len": out})
    return reqs

def gen_rag(seed, n_requests, doc_mean, doc_sd, tmpl_len, q_len, out_mean, rate):
    rng = random.Random(seed)
    template = words(rng, tmpl_len)          # shared instruction prefix
    t, reqs = 0.0, []
    for rid in range(n_requests):
        t += rng.expovariate(rate)
        doc = words(rng, max(800, int(rng.gauss(doc_mean, doc_sd))))
        q = words(rng, q_len)
        p = template + doc + q
        out = max(8, int(rng.gauss(out_mean, out_mean * 0.35)))
        reqs.append({"req_id": rid, "session": rid, "turn": 0,
                     "arrival_s": round(t, 3),
                     "prompt": " ".join(p), "prompt_len": len(p),
                     "output_len": out})
    return reqs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["chat", "rag"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--n", type=int, default=192)
    ap.add_argument("--rate", type=float, default=1.2)
    ap.add_argument("--prompt-mean", type=int, default=1300)
    ap.add_argument("--prompt-sd", type=int, default=300)
    ap.add_argument("--doc-mean", type=int, default=3800)
    ap.add_argument("--doc-sd", type=int, default=400)
    ap.add_argument("--tmpl-len", type=int, default=120)
    ap.add_argument("--q-len", type=int, default=80)
    ap.add_argument("--out-mean", type=int, default=180)
    ap.add_argument("--rag-out-mean", type=int, default=90)
    ap.add_argument("--rag-rate", type=float, default=0.55)
    a = ap.parse_args()
    if a.mode == "chat":
        reqs = gen_chat(a.seed, a.n, a.prompt_mean, a.prompt_sd, a.out_mean, a.rate)
    else:
        reqs = gen_rag(a.seed, a.n, a.doc_mean, a.doc_sd, a.tmpl_len,
                       a.q_len, a.rag_out_mean, a.rag_rate)
    with open(a.out, "w") as f:
        for r in reqs:
            f.write(json.dumps(r) + "\n")
    tot = sum(r["prompt_len"] for r in reqs)
    print(f"{a.mode}: {len(reqs)} req, {tot} prompt tok, span {reqs[-1]['arrival_s']:.0f}s -> {a.out}")

if __name__ == "__main__":
    main()
