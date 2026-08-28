#!/usr/bin/env bash
# Run 4: refit the per-step constant `a` on the ONLINE path.
# Starts the config-A server, drives it at fixed batch through the same
# httpx streaming client bench.py uses, refits `a` with b_p/b_d/c_kv frozen
# at their v0.3 offline values, and stops the server.
# usage: calibrate_online.sh
set -u
MODEL="${MODEL:-Qwen/Qwen3-32B-AWQ}"
source "$(pwd)/scripts/env.sh"

echo "=== [online-cal] stopping anything running ==="
bash scripts/stop_server.sh

echo "=== [online-cal] starting config-A server ==="
bash scripts/serve.sh A
pid=$(cat results/logs/server_A.pid)

echo "=== [online-cal] waiting for readiness ==="
if ! bash scripts/wait_ready.sh "results/logs/server_A.log" "$pid" 1200; then
  echo "[online-cal] SERVER FAILED TO BECOME READY"; exit 2
fi
grep -aoE "GPU KV cache size: [0-9,]+ tokens" results/logs/server_A.log | tail -1 \
  | tee results/logs/kv_pool_online_cal.txt

echo "=== [online-cal] calibrating ==="
cmd="python -m replay_sim.calibrate --mode online --model $MODEL \
--offline-perf results/perf_v03_offline.json --out results/perf_online_run4.json"
echo "$cmd" > results/logs/calibrate_online_cmd.txt
$cmd 2>&1 | tee results/logs/calibrate_online_run4.log
rc=${PIPESTATUS[0]}
echo "[online-cal] exit=$rc"

echo "=== [online-cal] stopping server ==="
bash scripts/stop_server.sh
exit $rc
