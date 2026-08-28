#!/usr/bin/env bash
# Stop the vLLM server AND any orphaned worker processes, then wait for VRAM
# to drain. A crashed engine leaves "VLLM::Worker_TPn" reparented to init,
# still holding the full KV allocation, which silently OOMs the next run.
pkill -f "vllm serve" 2>/dev/null
pkill -f "replay_sim.calibrate" 2>/dev/null
for i in $(seq 1 60); do
  pgrep -f "vllm serve" >/dev/null 2>&1 || break
  sleep 2
done
pkill -9 -f "vllm serve" 2>/dev/null
pkill -9 -f "VLLM::Worker" 2>/dev/null
pkill -9 -f "VLLM::EngineCore" 2>/dev/null
# any process still holding VRAM
for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
  if ps -o cmd= -p "$pid" 2>/dev/null | grep -qE "VLLM|vllm|python"; then
    echo "killing lingering GPU process $pid"; kill -9 "$pid" 2>/dev/null
  fi
done
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc)
  [ "$used" -lt 1500 ] && break
  sleep 2
done
echo "stopped; VRAM in use: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc) MiB; compute apps: $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)"
