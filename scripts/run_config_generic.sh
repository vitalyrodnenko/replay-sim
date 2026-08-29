#!/usr/bin/env bash
# Real-run an ARBITRARY (util, mbt, mns, pc) config with the standard protocol:
# strict VRAM drain -> fresh server -> /health gate -> assert the granted pool
# -> bench with --drop-first 10 --per-request -> teardown.
# usage: run_config_generic.sh <tag> <util> <mbt> <mns> <on|off> [expected_pool]
set -u
cd "$(dirname "$0")/.." || exit 1
tag="$1"; GMU="$2"; MBT="$3"; MNS="$4"; PC="$5"; WANT="${6:-}"
MODEL="Qwen/Qwen3-32B-AWQ"
OD=results/sweep/real
mkdir -p "$OD"
source scripts/env.sh
vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | paste -sd+ | bc 2>/dev/null; }

bash scripts/stop_server.sh >/dev/null 2>&1
for _ in $(seq 1 120); do
  u=$(vram); [ -n "$u" ] && [ "$u" -lt 450 ] 2>/dev/null && break; sleep 2
done
echo "[$tag] vram before boot: $(vram) MiB"

bash scripts/serve_generic.sh "sw_$tag" "$GMU" "$MBT" "$MNS" "$PC" >/dev/null 2>&1
pid=$(cat "results/logs/server_sw_${tag}.pid" 2>/dev/null)
if [ -z "$pid" ] || ! bash scripts/wait_ready.sh "results/logs/server_sw_${tag}.log" "$pid" 420; then
  echo "[$tag] SERVER FAILED TO BECOME READY"
  cp "results/logs/server_sw_${tag}.log" "$OD/failed_${tag}.log" 2>/dev/null
  bash scripts/stop_server.sh >/dev/null 2>&1; exit 2
fi
pool=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_sw_${tag}.log" \
       | tail -1 | grep -oE '[0-9,]+' | tr -d ',')
echo "[$tag] granted pool: $pool tokens ($((pool/16)) blocks)"
if [ -n "$WANT" ] && [ "$pool" != "$WANT" ]; then
  echo "[$tag] POOL MISMATCH: got $pool want $WANT -- recording and continuing"
fi
echo "$tag,$GMU,$MBT,$MNS,$PC,$pool,${WANT:-}" >> "$OD/pools.csv"

timeout -k 30 600 python -m replay_sim.bench --trace results/trace.jsonl --model "$MODEL" \
  --drop-first 10 --per-request "$OD/realpr_${tag}.jsonl" --out "$OD/real_${tag}.json" \
  > "$OD/bench_${tag}.log" 2>&1
rc=$?
cp "results/logs/server_sw_${tag}.log" "$OD/server_${tag}.log" 2>/dev/null
bash scripts/stop_server.sh >/dev/null 2>&1
rm -f "results/logs/server_sw_${tag}.log" "results/logs/server_sw_${tag}.pid" \
      "results/logs/serve_cmd_sw_${tag}.txt" 2>/dev/null
echo "[$tag] bench rc=$rc"
[ $rc -eq 0 ] && cat "$OD/real_${tag}.json"
exit $rc
