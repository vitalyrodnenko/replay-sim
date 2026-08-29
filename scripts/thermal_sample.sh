#!/usr/bin/env bash
# Night-long nvidia-smi sampler: temperature, SM/memory clocks, power, and
# throttle reasons. usage: thermal_sample.sh <outfile> [interval_s]
out="$1"; iv="${2:-60}"
Q="timestamp,index,temperature.gpu,clocks.sm,clocks.mem,power.draw,utilization.gpu,memory.used,clocks_event_reasons.active"
echo "# $Q" > "$out"
while true; do
  nvidia-smi --query-gpu="$Q" --format=csv,noheader,nounits >> "$out" 2>/dev/null
  sleep "$iv"
done
