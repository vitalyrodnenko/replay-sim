#!/usr/bin/env bash
# Start the vLLM server for one config, recording the exact command used.
# usage: serve.sh <A|B|Bprime|C> [gpu_mem_util_override]
set -u
cfg="$1"
MODEL="${MODEL:-Qwen/Qwen3-32B-AWQ}"
VENV="$(pwd)/.venv/bin"
export PATH="$VENV:$PATH"
source "$(pwd)/scripts/env.sh"
# NOTE: A/B default to 0.85, not the RUNBOOK's 0.90: 0.90 OOMs non-deterministically
# in CUDA graph capture on this box (run 1 and run 2 both). Every prediction since
# run 1 has been made against the 0.85 pool.
MNS=128
case "$cfg" in
  A)      GMU="${2:-0.85}"; MBT=2048; PC="--enable-prefix-caching" ;;
  B)      GMU="${2:-0.85}"; MBT=2048; PC="--no-enable-prefix-caching" ;;
  Bprime) GMU="${2:-0.90}"; MBT=8192; PC="--enable-prefix-caching" ;;
  C)      GMU="${2:-0.60}"; MBT=2048; PC="--enable-prefix-caching" ;;
  D)      GMU="${2:-0.85}"; MBT=2048; PC="--enable-prefix-caching"; MNS=32 ;;
  E)      GMU="${2:-0.70}"; MBT=2048; PC="--enable-prefix-caching" ;;
  F)      GMU="${2:-0.78}"; MBT=2048; PC="--enable-prefix-caching" ;;
  G)      GMU="${2:-0.85}"; MBT=8192; PC="--enable-prefix-caching" ;;
  *) echo "unknown config: $cfg" >&2; exit 1 ;;
esac

CMD="$VENV/vllm serve $MODEL --port 8000 --tensor-parallel-size 2 \
--max-model-len 8192 --max-num-seqs $MNS \
--gpu-memory-utilization $GMU --max-num-batched-tokens $MBT $PC"

log="results/logs/server_${cfg}.log"
printf '%s\n' "$CMD" > "results/logs/serve_cmd_${cfg}.txt"
echo "# started $(date -Is)" > "$log"
echo "# cmd: $CMD" >> "$log"
nohup $CMD >> "$log" 2>&1 &
echo $! > "results/logs/server_${cfg}.pid"
echo "started config $cfg (gpu-mem-util=$GMU, max-num-batched-tokens=$MBT, $PC) pid=$(cat results/logs/server_${cfg}.pid)"
