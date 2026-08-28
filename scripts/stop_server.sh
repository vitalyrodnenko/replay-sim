#!/usr/bin/env bash
# Stop the vLLM server AND any orphaned workers, then wait for VRAM to drain.
# A crashed engine leaves "VLLM::Worker_TPn" reparented to init still holding
# the full KV allocation, which silently OOMs the next run.
#
# NOTE: pkill -f matches ANY command line containing the pattern - including
# the shell that invoked this script, if that command line mentions e.g.
# "replay_sim.calibrate". Build an exclusion set of our own ancestry first.
selfset=" "
p=$$
while [ -n "$p" ] && [ "$p" != "1" ]; do
  selfset="$selfset$p "
  p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
done

kill_matching() {
  local pat="$1" sig="$2"
  for pid in $(pgrep -f "$pat" 2>/dev/null); do
    case "$selfset" in *" $pid "*) continue ;; esac
    kill "$sig" "$pid" 2>/dev/null
  done
}

kill_matching "vllm serve" -TERM
kill_matching "replay_sim\.calibrate" -TERM
for i in $(seq 1 60); do
  still=0
  for pid in $(pgrep -f "vllm serve" 2>/dev/null); do
    case "$selfset" in *" $pid "*) continue ;; esac
    still=1
  done
  [ "$still" = "0" ] && break
  sleep 2
done
kill_matching "vllm serve" -KILL
kill_matching "VLLM::" -KILL

# anything still holding VRAM
for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
  case "$selfset" in *" $pid "*) continue ;; esac
  echo "killing lingering GPU process $pid"
  kill -9 "$pid" 2>/dev/null
done
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc)
  [ "$used" -lt 1500 ] && break
  sleep 2
done
echo "stopped; VRAM in use: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc) MiB; compute apps: $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)"
