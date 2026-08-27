#!/usr/bin/env bash
# Wait for the vLLM server to become ready, or for its log to show a fatal error.
# usage: wait_ready.sh <server_log> <server_pid> [max_wait_s]
log="$1"; pid="$2"; maxw="${3:-3600}"
start=$(date +%s)
while true; do
  if curl -s -f -m 5 http://localhost:8000/health >/dev/null 2>&1; then
    echo "READY after $(( $(date +%s) - start ))s"; exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "SERVER_DIED after $(( $(date +%s) - start ))s"; exit 2
  fi
  if [ $(( $(date +%s) - start )) -gt "$maxw" ]; then
    echo "TIMEOUT after ${maxw}s"; exit 3
  fi
  sleep 5
done
