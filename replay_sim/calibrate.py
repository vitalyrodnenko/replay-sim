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
# Decode fit grid, run 5: batch AND context both swept, with kv = B*C
# decorrelated from B (at B=8: kv 4k/16k/32k; at B=16: 16k/65k; at B=64:
# 32k/49k). Peak KV per point is B*(ctx+gen) <= 74k against config A's
# 87,200-token pool, so no point runs near enough to preempt.
ONLINE_GRID = [(1, 512), (1, 4096), (4, 4096),
               (8, 512), (8, 2048), (8, 4096),
               (16, 1024), (16, 4096),
               (32, 512), (32, 2048),
               (64, 512), (64, 768),
               (96, 512), (128, 256)]
# Held out of every fit, reported as the calibration's own test point.
ONLINE_CHECK = [(16, 3072)]
# Prefill sweep for b_p: single request, one token out, TTFT vs prompt
# length. ceil(C/mbt) varies 1..4 so the per-step constant is separable.
ONLINE_PREFILL = [256, 512, 1024, 2048, 3072, 4096, 6144, 7168]


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


async def _preemptions(client, base):
    """vLLM's preemption counter. A point that preempts is not a clean
    fixed-batch measurement, so every decode point is bracketed by this."""
    try:
        m = (await client.get(base + "/metrics", timeout=30)).text
    except Exception:
        return None
    for line in m.splitlines():
        if line.startswith("vllm:num_preemptions_total"):
            try:
                return float(line.split()[-1])
            except ValueError:
                return None
    return 0.0


async def _measure_prefill(client, a, rng, filler_id, C):
    """TTFT of a single request, no other load. One prefill, one decode step.

    Same client, same endpoint, same streaming path as the decode points and
    as bench.py -- so b_p lands on the online path too rather than being
    carried over from the offline LLM() fit.
    """
    ttfts = []
    for _ in range(a.repeats):
        ids = _prompt_ids(rng, C, filler_id)
        t0 = time.perf_counter()
        async with client.stream("POST", a.base + "/v1/completions", timeout=600,
                                 json={"model": a.model, "prompt": ids,
                                       "max_tokens": 1, "ignore_eos": True,
                                       "temperature": 0.0, "stream": True}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if line.startswith("data:") and line.strip() != "data: [DONE]":
                    ttfts.append(time.perf_counter() - t0)
                    break
    ttfts.sort()
    return {"ctx": C, "ttft_s": ttfts[len(ttfts) // 2],
            "reps_ms": [round(1000 * v, 3) for v in ttfts]}


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

        prefill = []
        if a.fit == "full":
            print("\n-- prefill sweep (single request, TTFT vs prompt) --")
            for C in ONLINE_PREFILL:
                m = await _measure_prefill(client, a, rng, filler_id, C)
                prefill.append(m)
                print(f"  online prefill ctx={C:>5}: {m['ttft_s']*1000:8.1f} ms "
                      f"(reps {m['reps_ms']})")
                await asyncio.sleep(a.settle_s)

        print("\n-- decode sweep (steady state at fixed batch) --")
        rows, checks = [], []
        for grid, sink in ((ONLINE_GRID, rows), (ONLINE_CHECK, checks)):
            for (B, C) in grid:
                reps = []
                p_before = await _preemptions(client, a.base)
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
                p_after = await _preemptions(client, a.base)
                preempted = (p_before is not None and p_after is not None
                             and p_after > p_before)
                if preempted:
                    print(f"  WARNING B={B} ctx={C}: engine preempted "
                          f"{p_after - p_before:.0f} time(s) during this point; "
                          f"it is NOT a clean fixed-batch measurement.")
                reps.sort(key=lambda m: m["step_s"])
                best = reps[len(reps) // 2]      # median rep
                best["reps_ms"] = [round(m["step_s"] * 1000, 3) for m in reps]
                best["preempted"] = bool(preempted)
                sink.append(best)
    return base_perf, rows, checks, prefill


def online_main(a):
    import asyncio
    import numpy as np
    base_perf, rows, checks, prefill = asyncio.run(_online_run(a))
    b_p_off, b_d_off, c_kv_off = (base_perf["b_p"], base_perf["b_d"],
                                  base_perf["c_kv"])
    a_offline = base_perf["a"]

    prov = {"a_source": "online", "bd_ckv_source": "offline_v0.3_run3",
            "bp_source": "offline_v0.3_run3"}

    # ---------------- prefill: b_p on the online path ----------------
    b_p, prefill_fit = b_p_off, None
    if a.fit == "full" and prefill:
        # TTFT = d + a_p*ceil(C/mbt) + b_p*C : the per-step constant is
        # separable because the chunk count varies 1..4 across the sweep.
        A_ = np.array([[1.0, -(-C // a.mbt), C] for C in
                       [m["ctx"] for m in prefill]])
        y_ = np.array([m["ttft_s"] for m in prefill])
        coef, *_ = np.linalg.lstsq(A_, y_, rcond=None)
        d_p, a_p, b_p_on = coef.tolist()
        pred = A_ @ coef
        r2p = 1 - float(((y_ - pred) ** 2).sum()) / float(
            ((y_ - y_.mean()) ** 2).sum())
        print("\n== prefill fit (online) ==")
        print(f"{'ctx':>6} {'ttft ms':>9} {'fit ms':>9} {'resid ms':>9}")
        for m, pv in zip(prefill, pred):
            print(f"{m['ctx']:>6} {m['ttft_s']*1000:>9.1f} {pv*1000:>9.1f} "
                  f"{(m['ttft_s']-pv)*1000:>9.1f}")
        print(f"prefill fit R^2 = {r2p:.5f}   b_p = {b_p_on:.8f} "
              f"(offline {b_p_off:.8f}, {100*(b_p_on-b_p_off)/b_p_off:+.1f}%)")
        print(f"  per-chunk constant a_p = {a_p*1000:.2f} ms, "
              f"intercept d = {d_p*1000:.2f} ms")
        if b_p_on <= 0:
            print("WARNING: b_p fitted <= 0 online; keeping the offline value.")
        else:
            b_p = float(b_p_on)
            prov["bp_source"] = "online"
            prefill_fit = {"r2": round(r2p, 5), "b_p": b_p,
                           "a_per_chunk_ms": round(a_p * 1000, 4),
                           "intercept_ms": round(d_p * 1000, 4),
                           "points": [{"ctx": m["ctx"],
                                       "ttft_ms": round(m["ttft_s"] * 1000, 3),
                                       "reps_ms": m["reps_ms"]}
                                      for m in prefill]}

    # ---------------- decode: a, b_d, c_kv jointly ----------------
    clean = [m for m in rows if not m.get("preempted")]
    if len(clean) < len(rows):
        print(f"\nNOTE: {len(rows)-len(clean)} decode point(s) preempted and "
              f"are excluded from the fit.")
    A_ = np.array([[1.0, m["B"], m["B"] * m["ctx"] / 1e6] for m in clean])
    y_ = np.array([m["step_s"] for m in clean])

    if a.fit == "full":
        coef, *_ = np.linalg.lstsq(A_, y_, rcond=None)
        a_new, b_d, c_kv = coef.tolist()
        prov["bd_ckv_source"] = "online"
    else:                      # run-4 behaviour: intercept only
        b_d, c_kv = b_d_off, c_kv_off
        a_new = float(np.mean(y_ - b_d * A_[:, 1] - c_kv * A_[:, 2]))
        coef = np.array([a_new, b_d, c_kv])

    pred = A_ @ coef
    ss_res = float(((y_ - pred) ** 2).sum())
    ss_tot = float(((y_ - y_.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    print("\n== decode fit (online) ==")
    print(f"{'B':>4} {'ctx':>6} {'measured':>9} {'fit':>8} {'resid':>8} "
          f"{'resid %':>8}")
    for m, pv in zip(clean, pred):
        print(f"{m['B']:>4} {m['ctx']:>6} {m['step_s']*1000:>9.2f} "
              f"{pv*1000:>8.2f} {(m['step_s']-pv)*1000:>+8.2f} "
              f"{100*(pv-m['step_s'])/m['step_s']:>+7.1f}%")
    print(f"decode fit R^2 = {r2:.5f}")
    print(f"\n            {'a (ms)':>10} {'b_p':>13} {'b_d':>13} {'c_kv':>10}")
    print(f"v0.3 offline {a_offline*1000:>9.3f} {b_p_off:>13.8f} "
          f"{b_d_off:>13.8f} {c_kv_off:>10.5f}")
    print(f"v0.5 online  {a_new*1000:>9.3f} {b_p:>13.8f} "
          f"{b_d:>13.8f} {c_kv:>10.5f}")
    if c_kv <= 0:
        print("WARNING: c_kv fitted <= 0 online. The grid still cannot "
              "identify the KV term. Record before predicting.")

    # ---------------- held-out check point ----------------
    check = []
    for m in checks:
        p_new = a_new + b_d * m["B"] + c_kv * (m["B"] * m["ctx"]) / 1e6
        p_v03 = a_offline + b_d_off * m["B"] + c_kv_off * (m["B"] * m["ctx"]) / 1e6
        p_v04 = 0.0161107 + b_d_off * m["B"] + c_kv_off * (m["B"] * m["ctx"]) / 1e6
        e_new = 100 * (p_new - m["step_s"]) / m["step_s"]
        print(f"\nHELD-OUT CHECK POINT B={m['B']} ctx={m['ctx']}: "
              f"measured {m['step_s']*1000:.2f} ms")
        print(f"  v0.3 model {p_v03*1000:6.2f} ms  "
              f"({100*(p_v03-m['step_s'])/m['step_s']:+.1f}%)")
        print(f"  v0.4 model {p_v04*1000:6.2f} ms  "
              f"({100*(p_v04-m['step_s'])/m['step_s']:+.1f}%)")
        print(f"  v0.5 model {p_new*1000:6.2f} ms  ({e_new:+.1f}%)  <-- this run")
        check.append({"B": m["B"], "ctx": m["ctx"],
                      "step_ms": round(m["step_s"] * 1000, 3),
                      "v03_pred_ms": round(p_v03 * 1000, 3),
                      "v04_pred_ms": round(p_v04 * 1000, 3),
                      "v05_pred_ms": round(p_new * 1000, 3),
                      "v05_err_pct": round(e_new, 2)})

    perf = {"a": float(a_new), "b_p": float(b_p),
            "b_d": float(b_d), "c_kv": float(c_kv), **prov,
            "note": ("v0.5: every coefficient this harness can reach is "
                     "fitted on the vLLM OpenAI HTTP server with stream=True, "
                     "the path bench.py measures. Decode coefficients come "
                     "from steady-state inter-token intervals inside a window "
                     "where all B streams are co-resident; b_p from TTFT of a "
                     "single unloaded request. kv_read convention is B*C. "
                     "B=16/ctx=3072 is held out of every fit."),
            "online_fit": {
                "mode": a.fit,
                "decode_r2": round(r2, 5),
                "grid": [{"B": m["B"], "ctx": m["ctx"],
                          "step_ms": round(m["step_s"] * 1000, 3),
                          "median_itl_ms": round(m["median_itl_s"] * 1000, 3),
                          "reps_ms": m["reps_ms"],
                          "preempted": m.get("preempted", False)} for m in rows],
                "held_out_check": check,
                "prefill_fit": prefill_fit,
                "gen_tokens": a.gen_tokens, "warm_tokens": a.warm_tokens,
                "tail_tokens": a.tail_tokens, "repeats": a.repeats}}
    json.dump(perf, open(a.out, "w"), indent=2)
    print("\nperf model:", json.dumps({k: v for k, v in perf.items()
                                       if k != "online_fit"}, indent=2))
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
    ap.add_argument("--fit", choices=["a", "full"], default="full",
                    help="'a': run-4 behaviour, refit the intercept only. "
                         "'full': refit a, b_d, c_kv from the decode "
                         "sweep and b_p from the prefill sweep.")
    ap.add_argument("--mbt", type=int, default=2048,
                    help="server --max-num-batched-tokens, for the "
                         "prefill chunk count in the b_p fit")
    a = ap.parse_args()
    (online_main if a.mode == "online" else offline_main)(a)


if __name__ == "__main__":
    main()
