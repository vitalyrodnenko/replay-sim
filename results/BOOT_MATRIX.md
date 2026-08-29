# BOOT_MATRIX — does the VRAM drain threshold determine the KV pool?

**Date:** 2026-08-29  
**No simulator, `perf.json`, or verdict change.**

`results/NOISE_PLAN.md` recorded that booting identical settings twice granted 82,656 and 87,680 KV tokens — a 5,024-token spread with no config change — and left the mechanism unresolved. This matrix tests one candidate directly: the VRAM drain threshold used before the boot.

## Method

Config-A settings (`--gpu-memory-utilization 0.85 --max-num-batched-tokens 2048 --max-num-seqs 128 --enable-prefix-caching`, TP=2, Qwen3-32B-AWQ), booted 10 times, alternating two teardown regimes:

- **strict** — wait until total VRAM across both GPUs is below **450 MiB** (the idle floor with the desktop session is 255 MiB)
- **loose** — `stop_server.sh`'s original behaviour: proceed as soon as total VRAM is below **1500 MiB**

Every boot in this matrix has a **warm** compile/CUDA-graph cache: this shape has been booted dozens of times on this box. The matrix therefore isolates the drain variable only, and says nothing about a genuinely cold shape.

## Raw results

| boot | mode | VRAM before (MiB) | granted pool (tokens) | vs expected | ready |
|---|---|---|---|---|---|
| 1 | strict | 255 | 87,200 | +0 | 35s |
| 2 | loose | 255 | 87,200 | +0 | 36s |
| 3 | strict | 255 | 87,200 | +0 | 40s |
| 4 | loose | 255 | 87,200 | +0 | 35s |
| 5 | strict | 255 | 87,200 | +0 | 35s |
| 6 | loose | 255 | 87,200 | +0 | 35s |
| 7 | strict | 255 | 87,200 | +0 | 35s |
| 8 | loose | 255 | 87,200 | +0 | 35s |
| 9 | strict | 255 | 87,200 | +0 | 35s |
| 10 | loose | 255 | 87,200 | +0 | 36s |

## Summary

| regime | n | distinct pools granted | spread | mean VRAM before |
|---|---|---|---|---|
| strict (<450 MiB) | 5 | 87,200 | 0 tokens | 255 MiB |
| loose (<1500 MiB) | 5 | 87,200 | 0 tokens | 255 MiB |

## Outcome

**Both regimes produced the expected 87,200 tokens on every boot.** This matrix did not reproduce the irreproducibility. The drain threshold is therefore not sufficient on its own to cause it, at least not with a warm shape cache and this box in this state.

---

## Extension 1 — forcing residual VRAM (beyond the specified matrix)

The specified matrix could not vary its own independent variable: `stop_server.sh` kills the server processes and *waits*, so the GPU is back to its 255 MiB idle floor before either the 450 MiB or the 1500 MiB threshold is ever evaluated. Both regimes were therefore the same experiment.

To create genuine residual VRAM, the server was SIGKILLed and restarted immediately, with 1–3 s of reclamation time:

| boot | VRAM before (MiB) | pool | ready | note |
|---|---|---|---|---|
| h_clean | 255 | 87200 | 36s | clean boot from idle |
| h_kill1s | 255 | 87200 | 35s | SIGKILL then 1s wait |
| h_kill2s | 255 | 87200 | 35s | SIGKILL then 2s wait |
| h_kill3s | 255 | 87200 | 35s | SIGKILL then 3s wait |

**Also negative.** Even one second after SIGKILL the driver had reclaimed everything: 255 MiB before every boot, 87,200 tokens every time. Residual VRAM is not reachable through this path on this box, and is therefore not the mechanism.

## Extension 2 — a never-before-booted shape. This reproduces it.

Every pool that varied during this work was a **novel `(max-num-batched-tokens, max-num-seqs)` shape**; every stable one had been booted before. Testing that directly, with the strict drain held constant on both boots:

| shape (mbt/mns) | boot | VRAM before | granted pool | ready |
|---|---|---|---|---|
| 1536/48 | 1 (first ever) | 255 MiB | **82,688** | 65s |
| 1536/48 | 2 (repeat) | 255 MiB | **88,096** | 30s |
| 3072/96 | 1 (first ever) | 255 MiB | **82,256** | 71s |
| 3072/96 | 2 (repeat) | 255 MiB | **86,528** | 40s |

| shape | pool gained on the 2nd boot | time saved on the 2nd boot |
|---|---|---|
| 1536/48 | **+5,408 tokens** | 35s faster |
| 3072/96 | **+4,272 tokens** | 31s faster |

**Reproduced and replicated.** On both novel shapes the first boot was granted 82,256–82,688 tokens and the second, byte-identical, boot was granted 4,272–5,408 more. The first boot also took 31–35 seconds longer to reach `/health`, which is the compile and CUDA-graph capture the second boot loads from cache. Memory held during that work is resident when vLLM profiles free memory to size the KV cache.

The drain threshold, the thing this matrix was built to test, is not involved: both boots drained to the same 255 MiB.

## What remains unexplained

Two points in the published series still do not fit. Config **D** (mns 32, run 2) was that shape's first boot and came in *high* (87,840); config **I** (mbt 8192, run 5) was a repeat after G and came in *low* (68,768, matching G's offset to 3 tokens). A first-boot-compilation story does not account for either, so the effect is reproducible on demand without being fully characterised.

