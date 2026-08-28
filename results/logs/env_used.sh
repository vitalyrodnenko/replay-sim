#!/usr/bin/env bash
# Environment shared by calibration and ALL benchmark runs, so the step-time
# model and the three real configs see an identical engine setup.
export PATH="$(pwd)/.venv/bin:$PATH"
# FlashInfer 0.6.16's JIT sampling kernel uses cub::BlockAdjacentDifference::
# FlagHeads, removed in CCCL 3.x (CUDA 13.0 here), so it fails to compile on
# this box. Use vLLM's PyTorch-native top-k/top-p sampler instead. The bench
# runs greedy (temperature=0.0) and this is identical across A/B/C.
export VLLM_USE_FLASHINFER_SAMPLER=0
