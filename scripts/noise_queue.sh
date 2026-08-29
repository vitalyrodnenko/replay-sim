#!/usr/bin/env bash
# Overnight benchmark-noise queue. Design pre-registered in results/NOISE_PLAN.md
# (committed before this ever ran), with the amendment recorded in that file.
#
#   config A and J, alternating A,J,A,J,... REPEATS times each
#   full server restart per repeat, strict VRAM drain, /health gate,
#   --drop-first 10, --per-request, one retry on a dirty attempt then skip
#
# usage: noise_queue.sh [repeats]
set -u
cd "$(dirname "$0")/.." || exit 1

MODEL="Qwen/Qwen3-32B-AWQ"
REPEATS="${1:-14}"
ND=results/noise
QLOG="$ND/queue_log.txt"
DEADLINE_S="${DEADLINE_S:-25200}"          # 7 h hard wall-clock budget
BENCH_TIMEOUT_S="${BENCH_TIMEOUT_S:-600}"  # ~3.6x the ~166 s nominal bench
READY_TIMEOUT_S="${READY_TIMEOUT_S:-420}"  # ~12x the ~35 s nominal startup
DRAIN_MIB="${DRAIN_MIB:-450}"              # idle floor on this box is 255 MiB (desktop on GPU0)
MAX_CONSEC_SKIP="${MAX_CONSEC_SKIP:-4}"
mkdir -p "$ND" results/thermal
source scripts/env.sh

# expected KV pool per config, from the published series' own startup logs
declare -A EXPECT_POOL=( [A]=87200 [J]=81424 )

START_EPOCH=$(date +%s)
ts()   { date -Is; }
qlog() { echo "$(ts) $*" | tee -a "$QLOG"; }
vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | paste -sd+ | bc 2>/dev/null; }

# ---- single-instance lock: two drivers would fight over port 8000 ----------
exec 9>"$ND/.lock"
if ! flock -n 9; then
  echo "another noise_queue.sh already holds $ND/.lock -- refusing to start" >&2
  exit 1
fi

# ---- thermal sampler: APPEND, never truncate the night's record ------------
bash scripts/thermal_sample.sh results/thermal/thermal_night.csv 60 &
THERMPID=$!

STOPPING=0
cleanup() {
  [ "$STOPPING" = "1" ] && return
  STOPPING=1
  kill "$THERMPID" 2>/dev/null
  pkill -f "scripts/nvsample.sh" 2>/dev/null
  bash scripts/stop_server.sh >>"$ND/teardown.log" 2>&1
  qlog "QUEUE_EXIT"
}
on_signal() { qlog "SIGNAL received -- stopping"; cleanup; exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

# ---- strict VRAM drain -----------------------------------------------------
# The default stop_server.sh returns once total VRAM is under 1500 MiB. On this
# box ~1281 MiB of residue is worth ~5,000 KV tokens, which is the same size as
# the A-J pool difference itself, so a loose drain can silently turn an A boot
# into something indistinguishable from J. See results/vram_pool_test.csv.
strict_drain() {
  local u
  for _ in $(seq 1 120); do
    u=$(vram)
    if [ -n "$u" ] && [ "$u" -eq "$u" ] 2>/dev/null && [ "$u" -lt "$DRAIN_MIB" ]; then
      echo "$u"; return 0
    fi
    sleep 2
  done
  echo "${u:-unknown}"; return 1
}

# ---- one attempt: 0 = clean ------------------------------------------------
attempt() {
  local cfg="$1" rep="$2" att="$3"
  local tag; tag=$(printf '%s_%02d' "$cfg" "$rep")
  local stage="$ND/.stage_${tag}_att${att}"
  rm -rf "$stage"; mkdir -p "$stage"
  local t0; t0=$(date +%s)

  bash scripts/stop_server.sh >>"$ND/teardown.log" 2>&1
  local vres rc_drain
  vres=$(strict_drain); rc_drain=$?
  if [ $rc_drain -ne 0 ]; then
    qlog "$tag att=$att FAIL_DRAIN vram=${vres}MiB"; return 2
  fi

  # never touches results/logs/server_{A,J}.log -- those are published artifacts
  local stag="noise_${tag}_att${att}"
  bash scripts/serve_generic.sh "$stag" \
      "$(case $cfg in A) echo 0.85;; J) echo 0.82;; esac)" 2048 128 on \
      >>"$ND/serve.log" 2>&1
  local pid; pid=$(cat "results/logs/server_${stag}.pid" 2>/dev/null)
  if [ -z "$pid" ]; then qlog "$tag att=$att FAIL_NO_PID"; return 2; fi

  local rdy
  if ! rdy=$(bash scripts/wait_ready.sh "results/logs/server_${stag}.log" "$pid" "$READY_TIMEOUT_S"); then
    qlog "$tag att=$att FAIL_STARTUP ($rdy) vram_before=${vres}MiB"
    cp "results/logs/server_${stag}.log" "$ND/failed_${tag}_att${att}.log" 2>/dev/null
    bash scripts/stop_server.sh >>"$ND/teardown.log" 2>&1
    return 2
  fi
  local ready_s; ready_s=$(echo "$rdy" | grep -oE '[0-9]+' | head -1)

  local pool
  pool=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${stag}.log" \
         | tail -1 | grep -oE '[0-9,]+' | tr -d ',')
  local want="${EXPECT_POOL[$cfg]}"
  if [ "$pool" != "$want" ]; then
    qlog "$tag att=$att FAIL_POOL got=${pool:-none} want=$want vram_before=${vres}MiB"
    cp "results/logs/server_${stag}.log" "$ND/poolmismatch_${tag}_att${att}.log" 2>/dev/null
    bash scripts/stop_server.sh >>"$ND/teardown.log" 2>&1
    return 4
  fi

  local temp0
  temp0=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits | paste -sd'/')

  bash scripts/nvsample.sh "$stage/nv.csv" 5 &
  local nvpid=$!

  timeout -k 30 "$BENCH_TIMEOUT_S" \
    python -m replay_sim.bench --trace results/trace.jsonl --model "$MODEL" \
      --drop-first 10 --per-request "$stage/realpr.jsonl" \
      --out "$stage/real.json" > "$stage/bench.log" 2>&1
  local rc=$?
  kill "$nvpid" 2>/dev/null; pkill -P "$nvpid" 2>/dev/null

  curl -s -m 30 http://localhost:8000/metrics > "$stage/metrics.txt" 2>/dev/null
  cp "results/logs/server_${stag}.log" "$stage/server.log" 2>/dev/null
  bash scripts/stop_server.sh >>"$ND/teardown.log" 2>&1
  rm -f "results/logs/server_${stag}.log" "results/logs/server_${stag}.pid" \
        "results/logs/serve_cmd_${stag}.txt" 2>/dev/null

  local t1; t1=$(date +%s); local dur=$((t1 - t0))

  # ---- cleanliness gate (NOISE_PLAN section 3) ------------------------------
  if [ $rc -eq 124 ] || [ $rc -eq 137 ]; then
    qlog "$tag att=$att FAIL_BENCH_TIMEOUT after ${BENCH_TIMEOUT_S}s"; return 3
  fi
  if [ $rc -ne 0 ]; then qlog "$tag att=$att FAIL_BENCH rc=$rc dur=${dur}s"; return 3; fi
  if grep -qa "Traceback" "$stage/bench.log"; then
    qlog "$tag att=$att FAIL_TRACEBACK dur=${dur}s"; return 3
  fi
  local check
  check=$(python3 - "$stage" <<'PY'
import json, sys, os
d = sys.argv[1]
try:
    s = json.load(open(os.path.join(d, "real.json")))
except Exception as e:
    print(f"BAD_JSON:{e.__class__.__name__}"); raise SystemExit
need = ["ttft_p50_s","ttft_p95_s","e2e_p50_s","e2e_p95_s",
        "throughput_tok_s","prefix_cache_hit_rate"]
missing = [k for k in need if s.get(k) is None]
if missing: print("NULL_METRIC:" + ",".join(missing)); raise SystemExit
if s.get("requests") != 182: print(f"NREQ:{s.get('requests')}"); raise SystemExit
try:
    n = sum(1 for _ in open(os.path.join(d, "realpr.jsonl")))
except Exception:
    print("NO_PERREQ"); raise SystemExit
if n != 192: print(f"PERREQ_LINES:{n}"); raise SystemExit
print(f"OK {s['ttft_p95_s']} {s['prefix_cache_hit_rate']}")
PY
)
  case "$check" in
    OK*) : ;;
    *) qlog "$tag att=$att FAIL_GATE $check dur=${dur}s"; return 3 ;;
  esac

  # ---- promote: only a run that passed the gate gets a canonical name -------
  mv "$stage/real.json"     "$ND/real_${tag}.json"
  mv "$stage/realpr.jsonl"  "$ND/realpr_${tag}.jsonl"
  mv "$stage/bench.log"     "$ND/bench_${tag}.log"
  mv "$stage/metrics.txt"   "$ND/metrics_${tag}.txt"
  mv "$stage/server.log"    "$ND/server_${tag}.log"
  mv "$stage/nv.csv"        "results/thermal/nv_${tag}.csv" 2>/dev/null
  echo "$pool" > "$ND/kv_pool_${tag}.txt"
  rm -rf "$stage"

  echo "$tag,$att,$temp0,$ready_s,$pool,$vres,$dur" >> "$ND/run_context.csv"
  qlog "$tag att=$att CLEAN dur=${dur}s ready=${ready_s}s temp0=$temp0 pool=$pool ${check#OK }"
  return 0
}

# ---- main queue ------------------------------------------------------------
[ -f "$ND/run_context.csv" ] || echo "tag,attempt,temp_c,ready_s,pool_tokens,vram_before_mib,dur_s" > "$ND/run_context.csv"
qlog "QUEUE_START repeats=$REPEATS model=$MODEL drain=${DRAIN_MIB}MiB deadline=${DEADLINE_S}s trace_sha=$(sha256sum results/trace.jsonl | cut -c1-16)"

# discarded warm-up (see NOISE_PLAN amendment): cold page cache + idle GPUs
qlog "WARMUP starting discarded warm-up run (tag A_00, enters no statistic)"
attempt A 0 1 && qlog "WARMUP clean (discarded)" || qlog "WARMUP dirty (discarded anyway)"

clean_A=0; clean_J=0; consec_skip=0
for rep in $(seq 1 "$REPEATS"); do
  for cfg in A J; do
    if [ $(( $(date +%s) - START_EPOCH )) -gt "$DEADLINE_S" ]; then
      qlog "DEADLINE reached -- stopping with A=$clean_A J=$clean_J"; break 2
    fi
    ok=0
    for att in 1 2; do
      if attempt "$cfg" "$rep" "$att"; then ok=1; break; fi
      [ "$att" = "1" ] && qlog "$cfg rep=$rep attempt 1 dirty -- retrying once"
    done
    if [ "$ok" = "1" ]; then
      consec_skip=0
      if [ "$cfg" = "A" ]; then clean_A=$((clean_A+1)); else clean_J=$((clean_J+1)); fi
    else
      consec_skip=$((consec_skip+1))
      qlog "SKIP $cfg rep=$rep -- 2 attempts failed (consecutive skips: $consec_skip)"
      if [ "$consec_skip" -ge "$MAX_CONSEC_SKIP" ]; then
        qlog "BREAKER $consec_skip consecutive skips -- systemic fault, stopping"; break 2
      fi
    fi
    qlog "PROGRESS clean A=$clean_A J=$clean_J (rep $rep/$REPEATS)"
  done
done
qlog "QUEUE_DONE clean A=$clean_A J=$clean_J"
echo "QUEUEDONE A=$clean_A J=$clean_J" > "$ND/QUEUE_DONE"
