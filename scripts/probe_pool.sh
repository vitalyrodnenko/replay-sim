#!/usr/bin/env bash
# Probe one config's KV pool size from its own startup log, then shut down.
# Runs BEFORE predictions are frozen, exactly as runs 1-3 did.
# usage: probe_pool.sh <cfg>
set -u
cfg="$1"; shift || true
gmu="${1:-}"
source "$(pwd)/scripts/env.sh"
bash scripts/stop_server.sh >/dev/null
if [ -n "$gmu" ]; then bash scripts/serve.sh "$cfg" "$gmu" >/dev/null; else bash scripts/serve.sh "$cfg" >/dev/null; fi
pid=$(cat "results/logs/server_${cfg}.pid")
if ! bash scripts/wait_ready.sh "results/logs/server_${cfg}.log" "$pid" 900; then
  echo "PROBE ${cfg}${gmu:+ @ $gmu}: SERVER FAILED TO BECOME READY"
  cp "results/logs/server_${cfg}.log" "results/logs/probe_fail_${cfg}_${gmu:-default}.log"
  cp "results/logs/server_${cfg}.log" "results/logs/probe_fail_${cfg}.log"
  bash scripts/stop_server.sh >/dev/null
  exit 2
fi
n=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${cfg}.log" | tail -1)
echo "PROBE ${cfg}${gmu:+ @ $gmu}: ${n}"
echo "$n" > "results/logs/kv_pool_${cfg}_probe.txt"
bash scripts/stop_server.sh >/dev/null
