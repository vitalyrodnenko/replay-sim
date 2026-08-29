#!/usr/bin/env bash
# TASK 3: pool boot matrix. Boots config-A settings repeatedly under two drain
# regimes, alternating, recording the granted pool, pre-boot VRAM, and whether
# this was the shape's first boot since the driver was loaded.
# usage: boot_matrix.sh [pairs]
set -u
cd "$(dirname "$0")/.." || exit 1
PAIRS="${1:-5}"
OUT=results/boot_matrix.csv
LOG=results/logs/boot_matrix.log
DEADLINE_EPOCH="${DEADLINE_EPOCH:-0}"
source scripts/env.sh
echo "boot,mode,vram_before_mib,pool_tokens,ready_s,shape_cache_present,sys_uptime_s" > "$OUT"

vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | paste -sd+ | bc 2>/dev/null; }
# System uptime, recorded for context. NOTE: every boot in this matrix has a WARM
# shape cache -- the (0.85, 2048, 128) shape has been booted dozens of times in this
# repo already -- so this matrix isolates the DRAIN variable only. Recreating a true
# cold-shape state would mean deleting ~/.cache/vllm, which this batch does not do.
sys_uptime() { cut -d" " -f1 /proc/uptime 2>/dev/null | cut -d. -f1; }
shape_cache() { [ -d "$HOME/.cache/vllm/torch_compile_cache" ] && echo yes || echo no; }

strict_drain() { for _ in $(seq 1 120); do u=$(vram); [ -n "$u" ] && [ "$u" -eq "$u" ] 2>/dev/null && [ "$u" -lt 450 ] && return 0; sleep 2; done; return 1; }
loose_drain()  { for _ in $(seq 1 60);  do u=$(vram); [ -n "$u" ] && [ "$u" -eq "$u" ] 2>/dev/null && [ "$u" -lt 1500 ] && return 0; sleep 2; done; return 1; }

n=0
for p in $(seq 1 "$PAIRS"); do
  for mode in strict loose; do
    if [ "$DEADLINE_EPOCH" != "0" ] && [ "$(date +%s)" -gt "$DEADLINE_EPOCH" ]; then
      echo "DEADLINE reached at boot $n -- stopping" | tee -a "$LOG"; break 2
    fi
    n=$((n+1))
    bash scripts/stop_server.sh >/dev/null 2>&1
    if [ "$mode" = "strict" ]; then strict_drain; else loose_drain; fi
    before=$(vram)
    t0=$(date +%s)
    bash scripts/serve_generic.sh bm_$n 0.85 2048 128 on >/dev/null 2>&1
    pid=$(cat "results/logs/server_bm_$n.pid" 2>/dev/null)
    if [ -z "$pid" ] || ! bash scripts/wait_ready.sh "results/logs/server_bm_$n.log" "$pid" 420 >/dev/null 2>&1; then
      echo "$n,$mode,$before,BOOT_FAIL,,," | tee -a "$OUT"
      bash scripts/stop_server.sh >/dev/null 2>&1; continue
    fi
    ready=$(( $(date +%s) - t0 ))
    tok=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_bm_$n.log" | tail -1 | grep -oE '[0-9,]+' | tr -d ',')
    echo "$n,$mode,$before,$tok,$ready,$(shape_cache),$(sys_uptime)" | tee -a "$OUT"
    cp "results/logs/server_bm_$n.log" "results/logs/bootmatrix_$n.log" 2>/dev/null
    rm -f "results/logs/server_bm_$n.log" "results/logs/server_bm_$n.pid" "results/logs/serve_cmd_bm_$n.txt"
    bash scripts/stop_server.sh >/dev/null 2>&1
  done
done
echo "BOOT_MATRIX_DONE" | tee -a "$LOG"
