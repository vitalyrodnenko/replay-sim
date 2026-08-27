#!/usr/bin/env bash
# Stop any running vLLM server and wait for GPU memory to be released.
pkill -f "vllm serve" 2>/dev/null
for i in $(seq 1 120); do
  pgrep -f "vllm serve" >/dev/null 2>&1 || break
  sleep 2
done
if pgrep -f "vllm serve" >/dev/null 2>&1; then
  echo "escalating to SIGKILL"; pkill -9 -f "vllm serve"; sleep 10
fi
# wait for VRAM to drain
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc)
  [ "$used" -lt 1500 ] && break
  sleep 2
done
echo "stopped; total VRAM in use now: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc) MiB"
