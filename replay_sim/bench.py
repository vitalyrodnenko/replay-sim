"""Replay the trace against a running vLLM OpenAI server. RUN ON THE GPU BOX.

Respects arrival timestamps (open-loop load), streams to capture TTFT,
forces exact output lengths (max_tokens + ignore_eos) so the sim and the
real run generate identical token counts.

Start the server per config, e.g. config A:
  vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ --port 8000 \
      --max-model-len 8192 --gpu-memory-utilization 0.90 \
      --max-num-seqs 128 --max-num-batched-tokens 2048 \
      --enable-prefix-caching

Then:
  python -m replay_sim.bench --trace trace.jsonl --out real_A.json
"""
import argparse, asyncio, json, time

async def one(client, sem, base, model, r, results):
    async with sem:
        body = {
            "model": model, "prompt": r["prompt"],
            "max_tokens": r["output_len"], "ignore_eos": True,
            "temperature": 0.0, "stream": True,
        }
        t0 = time.perf_counter()
        ttft = None
        async with client.stream("POST", base + "/v1/completions",
                                 json=body, timeout=600) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data:") and line.strip() != "data: [DONE]":
                    if ttft is None:
                        ttft = time.perf_counter() - t0
        results[r["req_id"]] = {
            "ttft": ttft, "e2e": time.perf_counter() - t0,
            "prompt_len": r["prompt_len"], "output_len": r["output_len"],
        }

async def run(a):
    import httpx
    trace = [json.loads(l) for l in open(a.trace)]
    trace.sort(key=lambda r: r["arrival_s"])
    results = {}
    sem = asyncio.Semaphore(a.max_inflight)
    async with httpx.AsyncClient() as client:
        t_start = time.perf_counter()
        tasks = []
        for r in trace:
            delay = r["arrival_s"] / a.speedup - (time.perf_counter() - t_start)
            if delay > 0:
                await asyncio.sleep(delay)
            tasks.append(asyncio.create_task(
                one(client, sem, a.base, a.model, r, results)))
        await asyncio.gather(*tasks)
        makespan = time.perf_counter() - t_start

    # engine-side metrics (prefix cache hit rate) from /metrics
    hit = None
    try:
        m = (await httpx.AsyncClient().get(a.base.replace("/v1", "") + "/metrics")).text
        q = h = 0.0
        for line in m.splitlines():
            if line.startswith("vllm:prefix_cache_queries_total"):
                q = float(line.split()[-1])
            if line.startswith("vllm:prefix_cache_hits_total"):
                h = float(line.split()[-1])
        hit = (h / q) if q else None
    except Exception:
        pass

    ttfts = sorted(v["ttft"] for v in results.values())
    e2e = sorted(v["e2e"] for v in results.values())
    out_tok = sum(v["output_len"] for v in results.values())
    def p(v, q): return v[min(len(v) - 1, int(q * len(v)))]
    s = {
        "requests": len(results),
        "ttft_p50_s": round(p(ttfts, .5), 3), "ttft_p95_s": round(p(ttfts, .95), 3),
        "e2e_p50_s": round(p(e2e, .5), 3),   "e2e_p95_s": round(p(e2e, .95), 3),
        "throughput_tok_s": round(out_tok / makespan, 1),
        "makespan_s": round(makespan, 1),
        "prefix_cache_hit_rate": round(hit, 3) if hit is not None else None,
    }
    print(json.dumps(s, indent=2))
    json.dump(s, open(a.out, "w"), indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct-AWQ")
    ap.add_argument("--out", required=True)
    ap.add_argument("--speedup", type=float, default=1.0,
                    help=">1 compresses arrival times (heavier load)")
    ap.add_argument("--max-inflight", type=int, default=512)
    a = ap.parse_args()
    asyncio.run(run(a))

if __name__ == "__main__":
    main()
