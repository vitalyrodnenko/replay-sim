#!/usr/bin/env bash
# Pressure-ladder queue. Design pre-registered in results/LADDER_PLAN.md.
# Same protocol as the noise batch: strict VRAM drain, asserted KV pool,
# attempt-scoped staging, one retry then skip, single-instance lock.
# usage: ladder_queue.sh [repeats]
set -u
cd "$(dirname "$0")/.." || exit 1

MODEL="Qwen/Qwen3-32B-AWQ"
REPEATS="${1:-8}"
LD=results/ladder
QLOG="$LD/queue_log.txt"
PAIR_DEADLINE_EPOCH="${PAIR_DEADLINE_EPOCH:-0}"   # stop starting new pairs after this
BENCH_TIMEOUT_S="${BENCH_TIMEOUT_S:-900}"         # C may run slow under preemption
READY_TIMEOUT_S="${READY_TIMEOUT_S:-420}"
DRAIN_MIB="${DRAIN_MIB:-450}"
MAX_CONSEC_SKIP="${MAX_CONSEC_SKIP:-4}"
mkdir -p "$LD" results/thermal
source scripts/env.sh

declare -A EXPECT_POOL=( [K]=67936 [C]=39040 )
declare -A UTIL=( [K]=0.75 [C]=0.60 )

ts()   { date -Is; }
qlog() { echo "$(ts) $*" | tee -a "$QLOG"; }
vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | paste -sd+ | bc 2>/dev/null; }

exec 9>"$LD/.lock"
if ! flock -n 9; then echo "another ladder_queue.sh holds the lock" >&2; exit 1; fi

bash scripts/thermal_sample.sh results/thermal/thermal_ladder.csv 60 &
THERMPID=$!
STOPPING=0
cleanup() {
  [ "$STOPPING" = "1" ] && return
  STOPPING=1
  kill "$THERMPID" 2>/dev/null
  pkill -f "scripts/nvsample.sh" 2>/dev/null
  bash scripts/stop_server.sh >>"$LD/teardown.log" 2>&1
  qlog "QUEUE_EXIT"
}
on_signal() { qlog "SIGNAL received -- stopping"; cleanup; exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

strict_drain() {
  local u
  for _ in $(seq 1 120); do
    u=$(vram)
    if [ -n "$u" ] && [ "$u" -eq "$u" ] 2>/dev/null && [ "$u" -lt "$DRAIN_MIB" ]; then echo "$u"; return 0; fi
    sleep 2
  done
  echo "${u:-unknown}"; return 1
}

attempt() {
  local cfg="$1" rep="$2" att="$3"
  local tag; tag=$(printf '%s_%02d' "$cfg" "$rep")
  local stage="$LD/.stage_${tag}_att${att}"
  rm -rf "$stage"; mkdir -p "$stage"
  local t0; t0=$(date +%s)

  bash scripts/stop_server.sh >>"$LD/teardown.log" 2>&1
  local vres
  if ! vres=$(strict_drain); then qlog "$tag att=$att FAIL_DRAIN vram=${vres}MiB"; return 2; fi

  local stag="lad_${tag}_att${att}"
  bash scripts/serve_generic.sh "$stag" "${UTIL[$cfg]}" 2048 128 on >>"$LD/serve.log" 2>&1
  local pid; pid=$(cat "results/logs/server_${stag}.pid" 2>/dev/null)
  if [ -z "$pid" ]; then qlog "$tag att=$att FAIL_NO_PID"; return 2; fi

  local rdy
  if ! rdy=$(bash scripts/wait_ready.sh "results/logs/server_${stag}.log" "$pid" "$READY_TIMEOUT_S"); then
    qlog "$tag att=$att FAIL_STARTUP ($rdy)"
    cp "results/logs/server_${stag}.log" "$LD/failed_${tag}_att${att}.log" 2>/dev/null
    bash scripts/stop_server.sh >>"$LD/teardown.log" 2>&1; return 2
  fi
  local ready_s; ready_s=$(echo "$rdy" | grep -oE '[0-9]+' | head -1)

  local pool
  pool=$(grep -aoE "GPU KV cache size: [0-9,]+ tokens" "results/logs/server_${stag}.log" \
         | tail -1 | grep -oE '[0-9,]+' | tr -d ',')
  if [ "$pool" != "${EXPECT_POOL[$cfg]}" ]; then
    qlog "$tag att=$att FAIL_POOL got=${pool:-none} want=${EXPECT_POOL[$cfg]} vram_before=${vres}MiB"
    cp "results/logs/server_${stag}.log" "$LD/poolmismatch_${tag}_att${att}.log" 2>/dev/null
    bash scripts/stop_server.sh >>"$LD/teardown.log" 2>&1; return 4
  fi

  local temp0; temp0=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits | paste -sd'/')
  bash scripts/nvsample.sh "$stage/nv.csv" 5 & local nvpid=$!

  timeout -k 30 "$BENCH_TIMEOUT_S" \
    python -m replay_sim.bench --trace results/trace.jsonl --model "$MODEL" \
      --drop-first 10 --per-request "$stage/realpr.jsonl" \
      --out "$stage/real.json" > "$stage/bench.log" 2>&1
  local rc=$?
  kill "$nvpid" 2>/dev/null; pkill -P "$nvpid" 2>/dev/null

  curl -s -m 30 http://localhost:8000/metrics > "$stage/metrics.txt" 2>/dev/null
  cp "results/logs/server_${stag}.log" "$stage/server.log" 2>/dev/null
  bash scripts/stop_server.sh >>"$LD/teardown.log" 2>&1
  rm -f "results/logs/server_${stag}.log" "results/logs/server_${stag}.pid" \
        "results/logs/serve_cmd_${stag}.txt" 2>/dev/null
  local dur=$(( $(date +%s) - t0 ))

  if [ $rc -eq 124 ] || [ $rc -eq 137 ]; then qlog "$tag att=$att FAIL_BENCH_TIMEOUT ${BENCH_TIMEOUT_S}s"; return 3; fi
  if [ $rc -ne 0 ]; then qlog "$tag att=$att FAIL_BENCH rc=$rc dur=${dur}s"; return 3; fi
  if grep -qa "Traceback" "$stage/bench.log"; then qlog "$tag att=$att FAIL_TRACEBACK"; return 3; fi
  local check
  check=$(python3 - "$stage" <<'PY'
import json, sys, os
d = sys.argv[1]
try: s = json.load(open(os.path.join(d, "real.json")))
except Exception as e: print(f"BAD_JSON:{e.__class__.__name__}"); raise SystemExit
need = ["ttft_p50_s","ttft_p95_s","e2e_p50_s","e2e_p95_s","throughput_tok_s","prefix_cache_hit_rate"]
missing = [k for k in need if s.get(k) is None]
if missing: print("NULL_METRIC:" + ",".join(missing)); raise SystemExit
if s.get("requests") != 182: print(f"NREQ:{s.get('requests')}"); raise SystemExit
try: n = sum(1 for _ in open(os.path.join(d, "realpr.jsonl")))
except Exception: print("NO_PERREQ"); raise SystemExit
if n != 192: print(f"PERREQ_LINES:{n}"); raise SystemExit
print(f"OK {s['ttft_p95_s']} {s['prefix_cache_hit_rate']}")
PY
)
  case "$check" in OK*) : ;; *) qlog "$tag att=$att FAIL_GATE $check dur=${dur}s"; return 3 ;; esac

  mv "$stage/real.json"    "$LD/real_${tag}.json"
  mv "$stage/realpr.jsonl" "$LD/realpr_${tag}.jsonl"
  mv "$stage/bench.log"    "$LD/bench_${tag}.log"
  mv "$stage/metrics.txt"  "$LD/metrics_${tag}.txt"
  mv "$stage/server.log"   "$LD/server_${tag}.log"
  mv "$stage/nv.csv"       "results/thermal/nv_lad_${tag}.csv" 2>/dev/null
  echo "$pool" > "$LD/kv_pool_${tag}.txt"
  rm -rf "$stage"
  echo "$tag,$att,$temp0,$ready_s,$pool,$vres,$dur" >> "$LD/run_context.csv"
  qlog "$tag att=$att CLEAN dur=${dur}s ready=${ready_s}s temp0=$temp0 pool=$pool ${check#OK }"
  return 0
}

[ -f "$LD/run_context.csv" ] || echo "tag,attempt,temp_c,ready_s,pool_tokens,vram_before_mib,dur_s" > "$LD/run_context.csv"
qlog "QUEUE_START repeats=$REPEATS pair_deadline=$(date -d @"$PAIR_DEADLINE_EPOCH" +%H:%M 2>/dev/null) drain=${DRAIN_MIB}MiB"

qlog "WARMUP starting discarded warm-up (tag K_00, enters no statistic)"
attempt K 0 1 && qlog "WARMUP clean (discarded)" || qlog "WARMUP dirty (discarded anyway)"

declare -A CLEAN=( [K]=0 [C]=0 )
consec_skip=0
for rep in $(seq 1 "$REPEATS"); do
  now=$(date +%s)
  if [ "$PAIR_DEADLINE_EPOCH" != "0" ] && [ "$now" -gt "$PAIR_DEADLINE_EPOCH" ]; then
    qlog "PAIR_DEADLINE reached before rep $rep -- stopping with K=${CLEAN[K]} C=${CLEAN[C]}"
    break
  fi
  for cfg in K C; do
    ok=0
    for att in 1 2; do
      if attempt "$cfg" "$rep" "$att"; then ok=1; break; fi
      [ "$att" = "1" ] && qlog "$cfg rep=$rep attempt 1 dirty -- retrying once"
    done
    if [ "$ok" = "1" ]; then
      consec_skip=0; CLEAN[$cfg]=$(( ${CLEAN[$cfg]} + 1 ))
    else
      consec_skip=$((consec_skip+1))
      qlog "SKIP $cfg rep=$rep -- 2 attempts failed (consecutive: $consec_skip)"
      if [ "$consec_skip" -ge "$MAX_CONSEC_SKIP" ]; then
        qlog "BREAKER $consec_skip consecutive skips -- stopping"; break 2
      fi
    fi
    qlog "PROGRESS clean K=${CLEAN[K]} C=${CLEAN[C]} (rep $rep/$REPEATS)"
  done
done
qlog "QUEUE_DONE clean K=${CLEAN[K]} C=${CLEAN[C]}"
echo "LADDERDONE K=${CLEAN[K]} C=${CLEAN[C]}" > "$LD/QUEUE_DONE"
