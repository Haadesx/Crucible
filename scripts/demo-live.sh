#!/usr/bin/env bash
# DEMO LIVE — start a NEW real co-evolution run from scratch (writable state).
#
# Persistence  : DEV durable snapshot, new disposable run under
#                $TMPDIR/darwinguard-demo/live-<timestamp>/state.json. Nothing under
#                backend/experiments/ or backend/.dev-state*.json is used or touched.
# Mode         : WRITABLE RUN through the co-evolution CLI (real models). The observer API
#                stays read-only: it never writes the state, it only serves it. That is why
#                the API is relaunched after the CLI finishes — it holds an in-memory copy.
# API          : http://127.0.0.1:8000
# Frontend     : cd frontend && npm run dev -- --port 5175 --strictPort -> http://localhost:5175
#
# Safety       : refuses to boot if :8000 or :5175 is already listening (prints the owner and
#                exits non-zero), so a foreign observer (e.g. the Atlas one) can never be
#                mistaken for this run.
#
# Requirements : backend/.env with Red (ai-rig, qwen3.8-flash-next-heretic2) and Blue
#                (OpenRouter) credentials; the AI rig warm. One generation costs real
#                model calls: ~15-20 calls, 3-6 min with a warm rig (longer if not).
#
# Usage: scripts/demo-live.sh          # boot the stack, print the run command
#        scripts/demo-live.sh --run    # also execute one generation (real model spend)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
RUN_ID="DEMO-LIVE-$STAMP"
DEMO_DIR="${TMPDIR:-/tmp}/darwinguard-demo"
LIVE_DIR="$DEMO_DIR/live-$STAMP"
LIVE_STATE="$LIVE_DIR/state.json"
PORT=8000
FRONTEND_PORT=5175
LOG="$DEMO_DIR/live-api.log"
PIDFILE="$DEMO_DIR/live-api.pid"

mkdir -p "$LIVE_DIR/exports"

port_owner() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null || true
}

require_port_free() {
  local port="$1" purpose="$2" owner
  owner="$(port_owner "$port")"
  if [[ -n "$owner" ]]; then
    echo "ERROR: port :$port is already in use — refusing to start ($purpose)." >&2
    echo "$owner" >&2
    echo "That process would answer instead of ours, so the demo could show the wrong run." >&2
    echo "Stop the process above first, then re-run this script." >&2
    exit 1
  fi
}

stop_api() {
  if [[ -f "$PIDFILE" ]]; then
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 50); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
    fi
    rm -f "$PIDFILE"
  fi
}
trap stop_api EXIT

start_api() {
  require_port_free "$PORT" "the live observer API must own :$PORT"
  (
    cd "$BACKEND"
    # Pin the observer to the same JSON state the CLI writes. backend/.env may carry a
    # real MONGODB_URI; without this override build_container would serve Atlas while
    # the run lands in the tmp snapshot. The Atlas-backed live shape is a later change.
    DEV_STATE_PATH="$LIVE_STATE" MONGODB_URI= RUN_MODE=DEV TEST_MODE=false \
      .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
  )
  sleep 2
  echo "health: $(curl -s -m 3 "http://127.0.0.1:$PORT/health" || echo "not answering yet — check $LOG")"
}

stop_api
start_api

echo "DEMO LIVE — $RUN_ID"
echo "  persistence : DEV durable snapshot (fresh, writable by the CLI): $LIVE_STATE"
echo "  mode        : WRITABLE RUN via the co-evolution CLI; observer API is read-only"
echo "  API         : http://127.0.0.1:$PORT (log: $LOG)"
echo "  run command : (cd backend && DEV_STATE_PATH=$LIVE_STATE EXPORT_DIR=$LIVE_DIR/exports \\"
echo "                   MONGODB_URI= TEST_MODE=false .venv/bin/python -u -m app.coevolution \\"
echo "                   --generations 1 --run-id $RUN_ID --red-versions 2 \\"
echo "                   --attacks-per-version 1 --blue-candidates 2 --red-eval-attacks 1)"
echo "  expected UI : empty workspace until the run's first generation closes; after the"
echo "                CLI exits the API is relaunched, so the run is already loaded"
echo

if [[ "${1:-}" == "--run" ]]; then
  echo "running one REAL generation (model calls start now)…"
  (
    cd "$BACKEND"
    DEV_STATE_PATH="$LIVE_STATE" EXPORT_DIR="$LIVE_DIR/exports" MONGODB_URI= TEST_MODE=false \
      .venv/bin/python -u -m app.coevolution \
      --generations 1 --run-id "$RUN_ID" \
      --red-versions 2 --attacks-per-version 1 --blue-candidates 2 --red-eval-attacks 1
  )
  echo
  echo "run finished; relaunching the API so it reloads $RUN_ID…"
  stop_api
  start_api
fi

require_port_free "$FRONTEND_PORT" "the frontend must own :$FRONTEND_PORT"
echo "starting frontend dev server (Ctrl-C tears down the API too)…"
cd "$REPO_ROOT/frontend"
npm run dev -- --port "$FRONTEND_PORT" --strictPort
