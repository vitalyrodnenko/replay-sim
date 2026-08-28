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
  # run 5 held-out configs. H probes the pool axis above every point used so
  # far; 0.93 is above the 0.90 that OOMed in CUDA-graph capture in runs 1-2,
  # so H is expected to be the one that can fail to come up. I crosses pool
  # pressure with the coarse prefill budget for the first time.
  # H was specified at 0.93; 0.93 and 0.90 both die in CUDA-graph capture on
  # this box (results/logs/pool_ceiling_run5.txt). 0.88 is the highest bootable
  # point and is still above every utilisation used in runs 1-4 (max 0.85).
  H)      GMU="${2:-0.88}"; MBT=2048; PC="--enable-prefix-caching" ;;
  I)      GMU="${2:-0.78}"; MBT=8192; PC="--enable-prefix-caching" ;;
  # run 6 held-out config: an unseen pool point between F (0.78) and A (0.85).
  J)      GMU="${2:-0.82}"; MBT=2048; PC="--enable-prefix-caching" ;;
  # run 7 held-out config: the pressure zone, where partial vs full recompute
  # on eviction matters most. Unseen point between E (0.70) and F (0.78).
  K)      GMU="${2:-0.75}"; MBT=2048; PC="--enable-prefix-caching" ;;
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
