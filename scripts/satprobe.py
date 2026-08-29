"""TASK 1: saturation probe. Steady-state decode step cost at high batch.

Reuses replay_sim.calibrate's OWN _measure_point -- the run-5 method, the same
common-window construction, the same warm/tail token skips -- so these numbers are
directly comparable to the grid frozen in results/perf.json.

Reads perf.json; NEVER writes it. Fits nothing.

The one deviation, recorded per point: _measure_point holds B*(ctx+gen_tokens) KV
live. At gen_tokens=256 the point (128, 512) would need 98,304 tokens against config
A's 87,200-token pool and cannot be measured on this box at any bootable utilisation.
Points that would exceed 85% of the pool get a shorter gen_tokens, chosen to stay
under 95%, and the window length is reported alongside every measurement.
"""
import argparse, asyncio, json, os, sys, time
sys.path.insert(0, os.getcwd())
import httpx, random
from replay_sim.calibrate import _measure_point, _prompt_ids

GRID = [(96, 256), (96, 512), (112, 256), (112, 512), (128, 256), (128, 512), (32, 512)]
POOL = 87200
WARM, TAIL = 64, 8


class Args:
    pass


def gen_for(B, C):
    if B * (C + 256) <= 0.85 * POOL:
        return 256
    return max(96, min(256, int(0.95 * POOL / B) - C))


async def preemptions(base):
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(base + "/metrics", timeout=20)
        for line in r.text.splitlines():
            if line.startswith("vllm:num_preemptions_total"):
                return float(line.rsplit(" ", 1)[1])
    except Exception:
        pass
    return None


async def main_async(a):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    filler_id = tok(" hello", add_special_tokens=False)["input_ids"][-1]
    rng = random.Random(a.seed)
    out = []
    async with httpx.AsyncClient(
            limits=httpx.Limits(max_connections=256,
                                max_keepalive_connections=256)) as client:
        for (B, C) in GRID:
            a.gen_tokens = gen_for(B, C)
            reps = []
            pre0 = await preemptions(a.base)
            for i in range(a.repeats):
                await asyncio.sleep(a.settle_s)
                try:
                    m = await _measure_point(client, a, rng, filler_id, B, C)
                except Exception as e:
                    print(f"  B={B} ctx={C} rep{i}: FAILED {e.__class__.__name__}: {e}")
                    continue
                reps.append(m)
                print(f"  B={B:>3} ctx={C:>4} rep{i}: step {1000*m['step_s']:7.3f} ms "
                      f"(median itl {1000*m['median_itl_s']:6.2f}, "
                      f"spread {1000*m['spread_s']:5.2f}, win {m['window_steps']} steps)")
            pre1 = await preemptions(a.base)
            if not reps:
                out.append({"B": B, "ctx": C, "gen_tokens": a.gen_tokens, "failed": True})
                continue
            reps.sort(key=lambda m: m["step_s"])
            best = dict(reps[len(reps) // 2])
            best["reps_ms"] = [round(1000 * m["step_s"], 3) for m in reps]
            best["gen_tokens"] = a.gen_tokens
            best["peak_kv"] = B * (C + a.gen_tokens)
            best["peak_kv_pct"] = 100 * best["peak_kv"] / POOL
            best["preemptions_delta"] = (None if pre0 is None or pre1 is None
                                         else pre1 - pre0)
            out.append(best)
            print(f"  -> B={B} ctx={C}: median {1000*best['step_s']:.3f} ms  "
                  f"peakKV {best['peak_kv']:,} ({best['peak_kv_pct']:.0f}%)  "
                  f"preempt +{best['preemptions_delta']}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-32B-AWQ")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--settle-s", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=20260828)
    ap.add_argument("--out", default="results/satprobe/measurements.json")
    args = ap.parse_args()
    a = Args()
    a.model, a.base, a.repeats = args.model, args.base, args.repeats
    a.settle_s, a.seed = args.settle_s, args.seed
    a.warm_tokens, a.tail_tokens = WARM, TAIL
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = asyncio.run(main_async(a))
    json.dump({"grid": rows, "warm_tokens": WARM, "tail_tokens": TAIL,
               "pool_tokens": POOL, "method": "replay_sim.calibrate._measure_point (run-5)"},
              open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
