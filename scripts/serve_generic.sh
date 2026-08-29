#!/usr/bin/env bash
# Start vLLM with an ARBITRARY (util, mbt, mns, prefix-caching) combination.
# scripts/serve.sh only knows the lettered configs of the published series; the
# config sweep needs points that series never named.
# usage: serve_generic.sh <tag> <gpu_mem_util> <max_batched_tokens> <max_num_seqs> <on|off>
set -u
tag="$1"; GMU="$2"; MBT="$3"; MNS="$4"; PCFLAG="$5"
MODEL="${MODEL:-Qwen/Qwen3-32B-AWQ}"
VENV="$(pwd)/.venv/bin"
export PATH="$VENV:$PATH"
source "$(pwd)/scripts/env.sh"
case "$PCFLAG" in
  on)  PC="--enable-prefix-caching" ;;
  off) PC="--no-enable-prefix-caching" ;;
  *)   echo "prefix caching must be on|off, got: $PCFLAG" >&2; exit 1 ;;
esac
CMD="$VENV/vllm serve $MODEL --port 8000 --tensor-parallel-size 2 \
--max-model-len 8192 --max-num-seqs $MNS \
--gpu-memory-utilization $GMU --max-num-batched-tokens $MBT $PC"
log="results/logs/server_${tag}.log"
printf '%s\n' "$CMD" > "results/logs/serve_cmd_${tag}.txt"
echo "# started $(date -Is)" > "$log"
echo "# cmd: $CMD" >> "$log"
nohup $CMD >> "$log" 2>&1 &
echo $! > "results/logs/server_${tag}.pid"
echo "started $tag (util=$GMU mbt=$MBT mns=$MNS pc=$PCFLAG) pid=$(cat results/logs/server_${tag}.pid)"
