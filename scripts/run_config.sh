#!/usr/bin/env bash
# Full real-run cycle for one config: clean GPU -> start server -> wait for
# readiness -> sample nvidia-smi during the run -> bench.py -> stop.
# usage: run_config.sh <A|B|Bprime|C> [gpu_mem_util_override]
set -u
cfg="$1"; shift || true
gmu="${1:-}"
MODEL="Qwen/Qwen3-32B-AWQ"
source "$(pwd)/scripts/env.sh"

echo "=== [$cfg] stopping anything running ==="
bash scripts/stop_server.sh

echo "=== [$cfg] starting server ==="
if [ -n "$gmu" ]; then bash scripts/serve.sh "$cfg" "$gmu"; else bash scripts/serve.sh "$cfg"; fi
pid=$(cat "results/logs/server_${cfg}.pid")

echo "=== [$cfg] waiting for readiness ==="
if ! bash scripts/wait_ready.sh "results/logs/server_${cfg}.log" "$pid" 1200; then
  echo "[$cfg] SERVER FAILED TO BECOME READY"; exit 2
fi

# KV pool actually used by this run
grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${cfg}.log" | tail -1 \
  | tee "results/logs/kv_pool_${cfg}.txt"

echo "=== [$cfg] starting nvidia-smi sampler ==="
bash scripts/nvsample.sh "results/logs/nvidia_smi_${cfg}.csv" 5 &
nvpid=$!

echo "=== [$cfg] running bench.py ==="
benchcmd="python -m replay_sim.bench --trace results/trace.jsonl --model $MODEL --drop-first 10 --out results/real_${cfg}.json"
echo "$benchcmd" > "results/logs/bench_cmd_${cfg}.txt"
$benchcmd > "results/logs/bench_${cfg}.log" 2>&1
rc=$?
echo "[$cfg] bench exit=$rc"

kill "$nvpid" 2>/dev/null

echo "=== [$cfg] engine-side metrics snapshot ==="
curl -s -m 30 http://localhost:8000/metrics > "results/logs/metrics_${cfg}.txt" 2>/dev/null
grep -aE "^vllm:(prefix_cache|num_preemptions|gpu_cache_usage|kv_cache)" "results/logs/metrics_${cfg}.txt" | head -20

echo "=== [$cfg] stopping server ==="
bash scripts/stop_server.sh
exit $rc
