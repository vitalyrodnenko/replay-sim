#!/usr/bin/env bash
# Run 8a diagnostic bench: same server + bench as run_config.sh, but writes
# per-request dumps and a SEPARATE summary file. The canonical real_<cfg>.json
# used by the series is never touched.
# usage: run_config_diag.sh <cfg>
set -u
cfg="$1"
MODEL="Qwen/Qwen3-32B-AWQ"
source "$(pwd)/scripts/env.sh"

echo "=== [$cfg diag] stopping anything running ==="
bash scripts/stop_server.sh
echo "=== [$cfg diag] starting server ==="
bash scripts/serve.sh "$cfg"
pid=$(cat "results/logs/server_${cfg}.pid")
if ! bash scripts/wait_ready.sh "results/logs/server_${cfg}.log" "$pid" 1200; then
  echo "[$cfg diag] SERVER FAILED TO BECOME READY"; exit 2
fi
grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${cfg}.log" | tail -1 \
  | tee "results/logs/kv_pool_${cfg}_diag.txt"

echo "=== [$cfg diag] running bench.py --per-request ==="
cmd="python -m replay_sim.bench --trace results/trace.jsonl --model $MODEL --drop-first 10 \
--per-request results/diag/realpr_${cfg}.jsonl --out results/diag/real_${cfg}_diag.json"
echo "$cmd" > "results/logs/bench_cmd_${cfg}_diag.txt"
$cmd > "results/logs/bench_${cfg}_diag.log" 2>&1
rc=$?
echo "[$cfg diag] bench exit=$rc"
bash scripts/stop_server.sh
exit $rc
