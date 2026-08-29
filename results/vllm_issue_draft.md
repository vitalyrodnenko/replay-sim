# Draft upstream issue — NOT FILED

Draft only, from a single two-GPU box. Worth reproducing elsewhere before filing.

---

**Title:** First boot of a new `(max-num-batched-tokens, max-num-seqs)` shape is granted a ~5% smaller KV cache than subsequent identical boots

### Environment

- vLLM 0.28.0, V1 engine, TP=2
- 2 × NVIDIA RTX 4090 (24,564 MiB each), driver 580.173.02, CUDA 13.0
- Qwen/Qwen3-32B-AWQ, `--max-model-len 8192`
- Ubuntu 24.04, Python 3.12.3, `VLLM_USE_FLASHINFER_SAMPLER=0`, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

### Summary

Booting the server twice with byte-identical arguments gives two different `GPU KV cache size` values when the first boot is that shape's first ever. The second boot is granted roughly 5% more KV. The difference persists as long as the compile cache does, so a deployment's capacity depends on whether the cache happened to be warm when it started.

### Reproduction

Pick a `(--max-num-batched-tokens, --max-num-seqs)` pair this machine has never served, and boot it twice, waiting for GPU memory to return to idle in between so residual memory is not a factor:

```bash
drain() {  # wait for VRAM to return to idle before starting
  while [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits \
            | paste -sd+ | bc)" -ge 450 ]; do sleep 2; done
}

for i in 1 2; do
  drain
  vllm serve Qwen/Qwen3-32B-AWQ --port 8000 --tensor-parallel-size 2 \
    --max-model-len 8192 --max-num-batched-tokens 1536 --max-num-seqs 48 \
    --gpu-memory-utilization 0.85 --enable-prefix-caching &
  # wait for /health, then grep the log:
  #   grep -o 'GPU KV cache size: [0-9,]* tokens' server.log
  # ...then shut down
done
```

### Observed

Two independently chosen novel shapes, strict drain to 255 MiB before **both** boots:

| shape (mbt/mns) | boot 1 (first ever) | boot 2 (identical args) | difference | boot-1 startup | boot-2 startup |
|---|---|---|---|---|---|
| 1536/48 | 82,688 tokens | 88,096 tokens | **+5,408** | 65s | 30s |
| 3072/96 | 82,256 tokens | 86,528 tokens | **+4,272** | 71s | 40s |

The first boot is also ~30–35 s slower to reach `/health` — the compile and CUDA-graph capture that the second boot loads from `~/.cache/vllm/torch_compile_cache`.

### Why it matters

The KV pool is the main capacity parameter of a deployment, and this makes it depend on cache state rather than on the arguments. On this box the effect (~5,408 tokens) is **larger than the difference between `--gpu-memory-utilization 0.82` and `0.85`** (5,776 tokens), so two runs of the same configuration can straddle what was meant to be a deliberate configuration change. It is silent: the server starts normally and reports its pool as though the arguments determined it. Anyone A/B testing server configurations, or sizing capacity from a first deployment, inherits an uncontrolled ~5% term.

### Workaround

Boot each new shape once to populate the compile cache and discard that run, then measure. Waiting for VRAM to drain is *not* sufficient on its own — see below.

### What was ruled out

- **Residual GPU memory.** 10 boots alternating a strict drain (<450 MiB) with vLLM's default (<1500 MiB) gave 87,200 tokens every time. Forcing the issue with SIGKILL and a 1–3 s restart gave 87,200 every time as well; the driver had already reclaimed everything and pre-boot VRAM read 255 MiB in all 14 boots.
- **Utilisation, batched-token and sequence budgets** are held constant across each pair above.

### Caveats

- Single machine, single model, TP=2 only; not reproduced on other hardware.
- Two points from earlier work on this box do not fit a pure first-boot-compilation story: one shape's first boot came in high, and one repeat boot came in low. The effect reproduces on demand but is not fully characterised.
- The exact allocation being counted was not instrumented; the association with startup time is strong but indirect.

