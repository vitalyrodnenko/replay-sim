"""Fit the step-time model on real hardware. RUN ON THE GPU BOX.

Two modes.

OFFLINE (default, unchanged since v0.3) uses vLLM's offline LLM() API:
  1) prefill throughput at several chunk sizes  -> a, b_p
  2) decode step time at several (batch, ctx)   -> b_d, c_kv

ONLINE (--mode online, added for run 4) refits ONLY the per-step constant
`a` against the running OpenAI HTTP server, which is what bench.py measures.
Run-3 REPORT.md sec 7.1 found a ~5.6 ms/decode-step deficit invariant across
pool size and prefill budget, and hypothesised that `a` is fitted on the wrong
execution path: the offline engine pays no scheduler bookkeeping, incremental
detokenization, SSE framing or HTTP write, and the online server pays all four
on every step. This mode drives the server at a steady fixed batch, measures
the steady-state inter-token interval (== engine step time when B streams
decode in lockstep), and solves for the intercept with b_p, b_d and c_kv held
frozen at their offline values:

    a_online = mean_i [ t_i - b_d*B_i - c_kv*(B_i*C_i)/1e6 ]

The result is a HYBRID model and is labelled as such in perf.json
("a_source": "online", "bd_source": "offline"). kv_read is computed as B*C,
the same convention the offline decode fit used, so the frozen coefficients
stay meaningful.

Usage:
  # offline (unchanged)
  python -m replay_sim.calibrate --model $MODEL --tp 2 --out perf.json

  # online: server must already be running (scripts/serve.sh A)
  python -m replay_sim.calibrate --mode online --model $MODEL \
      --offline-perf results/perf_v03_offline.json --out results/perf.json
"""
import argparse, json, time

def offline_main(a):
    from vllm import LLM, SamplingParams
    import numpy as np

    llm = LLM(model=a.model, gpu_memory_utilization=a.gpu_mem_util,
              tensor_parallel_size=a.tp,
              max_model_len=a.max_model_len, enable_prefix_caching=False)
    tok = llm.get_tokenizer()
    filler = " ".join(["hello"] * a.max_model_len)

    def prompt_of(n_tok):
        ids = tok(filler)["input_ids"][:n_tok]
        return tok.decode(ids)

    # --- prefill: single sequence, one token out, varying prompt length
    xs, ys = [], []
    for n in [256, 512, 1024, 2048, 4096]:
        p = prompt_of(n)
        sp = SamplingParams(max_tokens=1, ignore_eos=True)
        llm.generate([p], sp)                      # warmup
        t0 = time.perf_counter()
        for _ in range(3):
            llm.generate([p], sp)
        dt = (time.perf_counter() - t0) / 3
        xs.append(n); ys.append(dt)
        print(f"prefill {n} tok: {dt*1000:.1f} ms")
    b_p, a_const = np.polyfit(xs, ys, 1)

    # --- decode: batch of B seqs at ctx C, generate 64 tokens, per-step time
    rows = []
    for B, C in [(1, 512), (8, 512), (8, 2048), (8, 4096), (16, 4096), (32, 512), (32, 2048), (64, 512), (64, 1024), (96, 512), (128, 256)]:
        p = prompt_of(C)
        sp = SamplingParams(max_tokens=64, ignore_eos=True)
        llm.generate([p] * B, sp)                  # warmup
        t0 = time.perf_counter()
        llm.generate([p] * B, sp)
        total = time.perf_counter() - t0
        # subtract modeled prefill time for B*C tokens (batched, approx)
        step = (total - (a_const + b_p * B * C)) / 64
        rows.append((B, B * C, step))
        print(f"decode B={B} ctx={C}: {step*1000:.2f} ms/step")
    import numpy as np2
    A = np2.array([[1.0, B, kv / 1e6] for (B, kv, _) in rows])
    y = np2.array([s for (_, _, s) in rows])
    coef, *_ = np2.linalg.lstsq(A, y, rcond=None)
    a2, b_d, c_kv = coef.tolist()

    pred = A @ coef
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    if c_kv <= 0:
        print("WARNING: c_kv fitted <= 0 (%.6f). The design matrix cannot "
              "identify the KV term; decode time will have no context "
              "dependence. Check grid coverage before predicting." % c_kv)
    print(f"decode fit R^2 = {r2:.5f}")
    perf = {"a": max(a_const, a2, 1e-4), "b_p": float(b_p),
            "b_d": float(max(b_d, 1e-6)), "c_kv": float(max(c_kv, 0.0))}
    json.dump(perf, open(a.out, "w"), indent=2)
    print("perf model:", json.dumps(perf, indent=2))
    print(f"wrote {a.out}")


# ---------------------------------------------------------------------------
# ONLINE MODE (run 4): refit `a` on the HTTP server path
# ---------------------------------------------------------------------------

# (batch, ctx) points. The first five are the fit grid; every one of them is
# also in the v0.3 offline decode grid, so online and offline step times are
# directly comparable at the same operating point. The last is a check point
# held out of the fit, at the trace's median prompt length.
ONLINE_GRID = [(1, 512), (8, 512), (8, 2048), (32, 512), (32, 2048)]
ONLINE_CHECK = [(16, 3072)]


def _prompt_ids(rng, n_tok, filler_id):
    """A prompt of exactly n_tok ids, unique per call.

    The first 16 ids are random, so the prefix-cache hash chain diverges at
    block 0 and no two streams (or repeats) share cached blocks. Config A runs
    with --enable-prefix-caching; the offline decode fit ran with prefix
    caching off, and this keeps the online measurement on the same footing.
    """
    head = [rng.randrange(1000, 100000) for _ in range(min(16, n_tok))]
    return head + [filler_id] * (n_tok - len(head))


async def _stream_one(client, base, model, prompt_ids, max_tokens):
    """One streaming completion. Returns client-side arrival time per token."""
    body = {"model": model, "prompt": prompt_ids, "max_tokens": max_tokens,
            "ignore_eos": True, "temperature": 0.0, "stream": True}
    ts = []
    async with client.stream("POST", base + "/v1/completions",
                             json=body, timeout=600) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("data:") and line.strip() != "data: [DONE]":
                ts.append(time.perf_counter())
    return ts


async def _measure_point(client, a, rng, filler_id, B, C):
    """Steady-state step time at batch B, context C.

    B streams of identical length decode in lockstep, so one engine step
    delivers one token to each stream and the per-stream inter-token interval
    IS the step time. Measured over a window that excludes the prefill ramp
    (first --warm-tokens) and the finishing tail (last --tail-tokens).
    """
    import asyncio
    T = a.gen_tokens
    prompts = [_prompt_ids(rng, C, filler_id) for _ in range(B)]
    res = await asyncio.gather(*[
        _stream_one(client, a.base, a.model, p, T) for p in prompts])

    bad = [len(ts) for ts in res if len(ts) != T]
    if bad:
        raise RuntimeError(f"B={B} ctx={C}: expected {T} token events per "
                           f"stream, got {sorted(set(bad))}")

    # Streams are staggered by the chunked-prefill ramp, so a per-stream token
    # window would not have all B streams co-resident. Take a COMMON wall-clock
    # window instead: it opens once the last stream is --warm-tokens into its
    # output and closes --tail-tokens before the first stream finishes, so
    # every step inside it ran at batch exactly B.
    lo, hi = a.warm_tokens, T - a.tail_tokens - 1
    t_lo = max(ts[lo] for ts in res)
    t_hi = min(ts[hi] for ts in res)
    if t_hi <= t_lo:
        raise RuntimeError(f"B={B} ctx={C}: no common steady-state window "
                           f"(ramp {(t_lo-min(ts[0] for ts in res)):.2f}s "
                           f"exceeds the run); raise --gen-tokens")

    per_stream, n_int = [], []
    for ts in res:
        i_lo = next(i for i, v in enumerate(ts) if v >= t_lo)
        i_hi = max(i for i, v in enumerate(ts) if v <= t_hi)
        if i_hi - i_lo < 20:
            raise RuntimeError(f"B={B} ctx={C}: only {i_hi-i_lo} steps in the "
                               f"common window; raise --gen-tokens")
        per_stream.append((ts[i_hi] - ts[i_lo]) / (i_hi - i_lo))
        n_int.append(i_hi - i_lo)
    step = sum(per_stream) / len(per_stream)

    # jitter diagnostics: median inter-token interval inside the same window,
    # and the prefill-ramp stagger the common window had to absorb
    deltas = sorted(ts[i] - ts[i - 1] for ts in res
                    for i in range(1, T)
                    if ts[i - 1] >= t_lo and ts[i] <= t_hi)
    med = deltas[len(deltas) // 2]
    return {"B": B, "ctx": C, "step_s": step, "median_itl_s": med,
            "spread_s": max(per_stream) - min(per_stream),
            "window_skew_s": max(ts[lo] for ts in res) - min(ts[lo] for ts in res),
            "window_steps": min(n_int), "samples": len(deltas)}


async def _online_run(a):
    import asyncio, httpx, random

    base_perf = json.load(open(a.offline_perf))
    b_p, b_d, c_kv = base_perf["b_p"], base_perf["b_d"], base_perf["c_kv"]
    a_offline = base_perf["a"]
    print(f"frozen from {a.offline_perf}: b_p={b_p:.8f} b_d={b_d:.8f} "
          f"c_kv={c_kv:.6f}   (offline a={a_offline:.6f}, to be replaced)")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    filler_id = tok(" hello", add_special_tokens=False)["input_ids"][-1]
    rng = random.Random(a.seed)

    async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=256,
                                max_keepalive_connections=256)) as client:
        # probe: confirm the server counts our token-id prompt at face value
        probe_n = 512
        r = await client.post(a.base + "/v1/completions", timeout=120, json={
            "model": a.model, "prompt": _prompt_ids(rng, probe_n, filler_id),
            "max_tokens": 1, "ignore_eos": True, "temperature": 0.0})
        r.raise_for_status()
        got = r.json().get("usage", {}).get("prompt_tokens")
        print(f"probe: sent {probe_n} token ids, server reports "
              f"prompt_tokens={got}")
        if got != probe_n:
            raise RuntimeError("server did not accept token-id prompts at face "
                               f"value ({got} != {probe_n}); cannot pin ctx")

        rows, checks = [], []
        for grid, sink in ((ONLINE_GRID, rows), (ONLINE_CHECK, checks)):
            for (B, C) in grid:
                reps = []
                for k in range(a.repeats):
                    m = await _measure_point(client, a, rng, filler_id, B, C)
                    reps.append(m)
                    print(f"  online B={B:>3} ctx={C:>4} rep{k}: "
                          f"{m['step_s']*1000:6.2f} ms/step  "
                          f"(median itl {m['median_itl_s']*1000:5.2f}, "
                          f"batch spread {m['spread_s']*1000:4.2f}, "
                          f"ramp skew {m['window_skew_s']*1000:6.0f} ms, "
                          f"win {m['window_steps']} steps, n={m['samples']})")
                    await asyncio.sleep(a.settle_s)
                reps.sort(key=lambda m: m["step_s"])
                best = reps[len(reps) // 2]      # median rep
                best["reps_ms"] = [round(m["step_s"] * 1000, 3) for m in reps]
                sink.append(best)
    return base_perf, rows, checks


def online_main(a):
    import asyncio
    base_perf, rows, checks = asyncio.run(_online_run(a))
    b_p, b_d, c_kv = base_perf["b_p"], base_perf["b_d"], base_perf["c_kv"]
    a_offline = base_perf["a"]

    def resid(m):
        return m["step_s"] - b_d * m["B"] - c_kv * (m["B"] * m["ctx"]) / 1e6

    def pred_old(m):
        return a_offline + b_d * m["B"] + c_kv * (m["B"] * m["ctx"]) / 1e6

    print("\n== per-point intercept ==")
    print(f"{'B':>4} {'ctx':>5} {'online ms':>10} {'v0.3 model ms':>14} "
          f"{'delta ms':>9} {'implied a ms':>13}")
    rs = []
    for m in rows:
        rs.append(resid(m))
        print(f"{m['B']:>4} {m['ctx']:>5} {m['step_s']*1000:10.2f} "
              f"{pred_old(m)*1000:14.2f} {(m['step_s']-pred_old(m))*1000:9.2f} "
              f"{resid(m)*1000:13.2f}")

    a_online = sum(rs) / len(rs)
    spread = max(rs) - min(rs)
    sd = (sum((r - a_online) ** 2 for r in rs) / max(1, len(rs) - 1)) ** 0.5
    print(f"\na_online = {a_online*1000:.3f} ms  (offline {a_offline*1000:.3f} "
          f"ms, delta {(a_online-a_offline)*1000:+.3f} ms)")
    print(f"intercept spread across the grid: {spread*1000:.3f} ms, "
          f"stdev {sd*1000:.3f} ms")
    if sd > 0.25 * abs(a_online):
        print("WARNING: the implied intercept is not constant across the grid; "
              "a single per-step constant does not describe the online "
              "overhead. Record this before predicting.")

    for m in checks:
        m_pred_new = a_online + b_d * m["B"] + c_kv * (m["B"] * m["ctx"]) / 1e6
        print(f"check point B={m['B']} ctx={m['ctx']}: online "
              f"{m['step_s']*1000:.2f} ms, v0.3 model {pred_old(m)*1000:.2f} ms, "
              f"hybrid model {m_pred_new*1000:.2f} ms "
              f"(hybrid err {100*(m_pred_new-m['step_s'])/m['step_s']:+.1f}%)")

    perf = {
        "a": float(a_online), "b_p": float(b_p),
        "b_d": float(b_d), "c_kv": float(c_kv),
        "a_source": "online",
        "bp_bd_ckv_source": "offline_v0.3_run3",
        "note": ("hybrid v0.4 model: the per-step constant `a` is refitted "
                 "against the vLLM OpenAI HTTP server with stream=True (the "
                 "path bench.py measures); b_p, b_d and c_kv are carried over "
                 "unchanged from the v0.3 offline LLM() fit. kv_read convention "
                 "for the refit is B*C, matching the offline decode fit."),
        "online_fit": {
            "grid": [{"B": m["B"], "ctx": m["ctx"],
                      "step_ms": round(m["step_s"] * 1000, 3),
                      "median_itl_ms": round(m["median_itl_s"] * 1000, 3),
                      "reps_ms": m["reps_ms"],
                      "implied_a_ms": round(resid(m) * 1000, 3)} for m in rows],
            "check_points": [{"B": m["B"], "ctx": m["ctx"],
                              "step_ms": round(m["step_s"] * 1000, 3)}
                             for m in checks],
            "a_offline_ms": round(a_offline * 1000, 4),
            "a_online_ms": round(a_online * 1000, 4),
            "delta_ms": round((a_online - a_offline) * 1000, 4),
            "intercept_stdev_ms": round(sd * 1000, 4),
            "gen_tokens": a.gen_tokens, "warm_tokens": a.warm_tokens,
            "tail_tokens": a.tail_tokens, "repeats": a.repeats,
        },
    }
    json.dump(perf, open(a.out, "w"), indent=2)
    print("\nperf model:", json.dumps(perf, indent=2))
    print(f"wrote {a.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "online"], default="offline")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="perf.json")
    # offline mode
    ap.add_argument("--gpu-mem-util", type=float, default=0.90)
    ap.add_argument("--tp", type=int, default=1, help="tensor parallel size")
    ap.add_argument("--max-model-len", type=int, default=8192)
    # online mode
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--offline-perf", default="results/perf_v03_offline.json",
                    help="perf.json supplying the frozen b_p, b_d, c_kv")
    ap.add_argument("--gen-tokens", type=int, default=256)
    ap.add_argument("--warm-tokens", type=int, default=64,
                    help="tokens to skip while the batch fills (prefill ramp)")
    ap.add_argument("--tail-tokens", type=int, default=8,
                    help="tokens to skip as streams finish and the batch drains")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--settle-s", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=20260828)
    a = ap.parse_args()
    (online_main if a.mode == "online" else offline_main)(a)


if __name__ == "__main__":
    main()
