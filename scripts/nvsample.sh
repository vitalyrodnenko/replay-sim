#!/usr/bin/env bash
# Periodic nvidia-smi snapshots. usage: nvsample.sh <outfile> [interval_s]
out="$1"; iv="${2:-5}"
echo "# timestamp, index, util.gpu[%], mem.used[MiB], mem.total[MiB], temp[C], power[W]" > "$out"
while true; do
  nvidia-smi --query-gpu=timestamp,index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw \
             --format=csv,noheader,nounits >> "$out"
  sleep "$iv"
done
