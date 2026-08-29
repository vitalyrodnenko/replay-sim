#!/usr/bin/env bash
# Boot an arbitrary config just far enough to read the KV pool it is granted,
# then shut down. Same discipline as scripts/probe_pool.sh, arbitrary params.
# usage: probe_pool_generic.sh <tag> <util> <mbt> <mns> <on|off>
set -u
cd "$(dirname "$0")/.." || exit 1
tag="$1"; GMU="$2"; MBT="$3"; MNS="$4"; PCFLAG="$5"
OUT=results/pool_probe.csv
[ -f "$OUT" ] || echo "tag,util,mbt,mns,pc,tokens,status" > "$OUT"
bash scripts/stop_server.sh >/dev/null 2>&1
bash scripts/serve_generic.sh "$tag" "$GMU" "$MBT" "$MNS" "$PCFLAG" >/dev/null 2>&1
pid=$(cat "results/logs/server_${tag}.pid" 2>/dev/null)
if [ -z "$pid" ] || ! bash scripts/wait_ready.sh "results/logs/server_${tag}.log" "$pid" 900 >/dev/null 2>&1; then
  echo "PROBE $tag (util=$GMU mbt=$MBT mns=$MNS pc=$PCFLAG): FAILED TO BOOT"
  cp "results/logs/server_${tag}.log" "results/logs/probe_fail_${tag}.log" 2>/dev/null
  echo "$tag,$GMU,$MBT,$MNS,$PCFLAG,,BOOT_FAIL" >> "$OUT"
  bash scripts/stop_server.sh >/dev/null 2>&1
  exit 2
fi
line=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${tag}.log" | tail -1)
tokens=$(echo "$line" | grep -oE '[0-9,]+' | tr -d ',')
echo "PROBE $tag (util=$GMU mbt=$MBT mns=$MNS pc=$PCFLAG): $tokens tokens"
echo "$tag,$GMU,$MBT,$MNS,$PCFLAG,$tokens,OK" >> "$OUT"
bash scripts/stop_server.sh >/dev/null 2>&1
