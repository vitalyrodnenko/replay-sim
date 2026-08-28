"""Fit the step-time model on real hardware. RUN ON THE GPU BOX.

Uses vLLM's offline API to measure:
  1) prefill throughput at several chunk sizes  -> a, b_p
  2) decode step time at several (batch, ctx)   -> b_d, c_kv

Writes perf.json consumed by simulator.py.

Usage (on the 4090 machine, inside a venv with vllm installed):
  python -m replay_sim.calibrate --model Qwen/Qwen2.5-7B-Instruct-AWQ \
      --gpu-mem-util 0.90 --out perf.json
"""
import argparse, json, time

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--gpu-mem-util", type=float, default=0.90)
    ap.add_argument("--tp", type=int, default=1, help="tensor parallel size")
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--out", default="perf.json")
    a = ap.parse_args()

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
    for B, C in [(1, 512), (8, 512), (32, 512), (8, 4096), (32, 2048), (64, 512), (96, 512), (128, 256)]:
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

    perf = {"a": max(a_const, a2, 1e-4), "b_p": float(b_p),
            "b_d": float(max(b_d, 1e-6)), "c_kv": float(max(c_kv, 0.0))}
    json.dump(perf, open(a.out, "w"), indent=2)
    print("perf model:", json.dumps(perf, indent=2))
    print(f"wrote {a.out}")

if __name__ == "__main__":
    main()
