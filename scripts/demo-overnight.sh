#!/usr/bin/env bash
# DEMO OVERNIGHT — DarwinGuard co-evolution, persisted evidence (7 generations / 256 calls).
#
# Persistence  : DEV durable snapshot, derived final report built read-only from the
#                historical run (backend/exports/derived/OVERNIGHT-COEV-20260926-022643/
#                state.final.json). The original experiment directory is never served.
# Mode         : READ-ONLY evidence. A disposable copy is served; Start/Reset are refused
#                by the observer guard, and the script proves that before printing READY.
# API          : http://127.0.0.1:8000
# Frontend     : cd frontend && npm run dev -- --port 5175 --strictPort -> http://localhost:5175
#
# Safety       : refuses to boot if :8000 or :5175 is already listening (prints the owner and
#                exits non-zero). After boot it verifies the health of the process it started,
#                that the repository is read-only, and that /runs lists THIS run id; if any
#                check fails it kills its own API and never prints READY. The API is started
#                detached, so it survives this script exiting in --api-only mode.
#
# Story        : G00 ASR 0.667 (two real breaches vs B0) -> Ling authors patch C1, promoted
#                (fitness 0.702 over 10 battles) -> C1 holds every attack in G01-G06
#                (ASR 0.0) while Red mutates 23 times (11 promoted / 12 rejected).
#
# Usage: scripts/demo-overnight.sh [--api-only]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
PY="$BACKEND/.venv/bin/python"
RUN_ID="OVERNIGHT-COEV-20260926-022643"
DERIVED_STATE="$BACKEND/exports/derived/$RUN_ID/state.final.json"
DEMO_DIR="${TMPDIR:-/tmp}/darwinguard-demo"
SERVED_STATE="$DEMO_DIR/overnight.state.json"
PORT=8000
FRONTEND_PORT=5175
LOG="$DEMO_DIR/overnight-api.log"
PIDFILE="$DEMO_DIR/overnight-api.pid"

API_PID=""

port_owner() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null || true
}

require_port_free() {
  local port="$1" purpose="$2" owner
  owner="$(port_owner "$port")"
  if [[ -n "$owner" ]]; then
    echo "ERROR: port :$port is already in use — refusing to start ($purpose)." >&2
    echo "$owner" >&2
    echo "That process would answer instead of ours, so this demo could show the wrong run." >&2
    echo "Stop the process above first, then re-run this script." >&2
    exit 1
  fi
}

stop_api() {
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
  API_PID=""
  rm -f "$PIDFILE"
}

kill_stale_api() {
  if [[ -f "$PIDFILE" ]]; then
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" -o command= 2>/dev/null | grep -q "uvicorn.*app.main:app"; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PIDFILE"
  fi
}

fail_verification() {
  echo "VERIFY FAILED: $1" >&2
  echo "  killing our API (pid ${API_PID:-none}); log: $LOG" >&2
  stop_api
  exit 1
}

wait_for_health() {
  local i
  for i in $(seq 1 60); do
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo "our API process (pid $API_PID) exited during startup; last log lines:" >&2
      tail -n 20 "$LOG" >&2 || true
      return 1
    fi
    if curl -fsS -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "our API did not answer /health within 30s; last log lines:" >&2
  tail -n 20 "$LOG" >&2 || true
  return 1
}

mkdir -p "$DEMO_DIR"

# A foreign listener on :8000 (e.g. the Atlas observer) must never be mistaken for ours.
require_port_free "$PORT" "the historical API must own :$PORT"

if [[ ! -f "$DERIVED_STATE" ]]; then
  echo "derived state missing: $DERIVED_STATE" >&2
  echo "rebuild it with:" >&2
  echo "  (cd backend && .venv/bin/python scripts/rebuild_run_report.py \\" >&2
  echo "     --state experiments/$RUN_ID/state.json --run-id $RUN_ID --out-dir exports/derived/$RUN_ID)" >&2
  exit 1
fi

# Serve a disposable copy so no click can ever touch a repository artifact.
cp "$DERIVED_STATE" "$SERVED_STATE"
kill_stale_api
trap stop_api EXIT

echo "DEMO OVERNIGHT — $RUN_ID"
echo "  persistence : DEV durable snapshot (derived final report; source evidence untouched)"
echo "  served copy : $SERVED_STATE"
echo "  mode        : READ-ONLY evidence — Start/Reset are not part of this demo"
echo "  API         : http://127.0.0.1:$PORT (log: $LOG)"
echo "  expected UI : 7 generations, 256 model calls, ASR 0.667 then 0.0 for G01-G06"
echo "  verifying   : :$PORT free, our process healthy, repository read-only, run id in /runs"
echo

# Detached (nohup + disown) so the API survives this script exiting in --api-only mode.
cd "$BACKEND"
# Pin snapshot mode: backend/.env may carry a real MONGODB_URI (Atlas), and
# build_container prefers Mongo whenever has_mongodb is true. The historical
# observer must serve the JSON evidence, never Atlas.
nohup env DEV_STATE_PATH="$SERVED_STATE" MONGODB_URI= RUN_MODE=DEV TEST_MODE=false \
  "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 &
API_PID=$!
cd "$REPO_ROOT"
disown "$API_PID" 2>/dev/null || true
echo "$API_PID" >"$PIDFILE"

if ! wait_for_health; then
  fail_verification "the API we started is not healthy"
fi

# Prove the server answering is ours and is serving THIS run, read-only.
status_json="$(curl -fsS -m 5 "http://127.0.0.1:$PORT/system/status")" \
  || fail_verification "GET /system/status failed"
parsed_status="$("$PY" -c '
import json, sys
status = json.load(sys.stdin)
value = status.get("read_only", None)
print(status.get("latest_run_id") or "-", "absent" if value is None else str(value).lower())
' <<<"$status_json")" || fail_verification "could not parse /system/status"
read -r latest_run_id read_only_value <<<"$parsed_status"

if [[ "$read_only_value" == "true" ]]; then
  echo "  read-only   : /system/status read_only=true"
elif [[ "$read_only_value" == "absent" ]]; then
  # /system/status does not expose read_only yet (Kiro finding 2, owned by ui-safety).
  # Absence is not proof: probe a no-body mutation. A read-only repository must answer
  # 409 READ_ONLY_SNAPSHOT; anything else means the served copy is writable.
  probe_code="$(curl -s -o "$DEMO_DIR/overnight-reset-probe.out" -w '%{http_code}' \
    -X POST "http://127.0.0.1:$PORT/arena/reset")" || probe_code="000"
  if [[ "$probe_code" != "409" ]]; then
    fail_verification "POST /arena/reset returned $probe_code, not 409 — served copy is NOT read-only"
  fi
  echo "  read-only   : /system/status lacks read_only; POST /arena/reset refused with 409"
else
  fail_verification "/system/status reports read_only=$read_only_value, expected true"
fi

if [[ "$latest_run_id" != "$RUN_ID" ]]; then
  fail_verification "/system/status latest_run_id is '$latest_run_id', expected '$RUN_ID'"
fi

runs_json="$(curl -fsS -m 5 "http://127.0.0.1:$PORT/runs")" \
  || fail_verification "GET /runs failed"
if ! printf '%s' "$runs_json" | "$PY" -c '
import json, sys
runs = json.load(sys.stdin)
sys.exit(0 if any(run.get("run_id") == sys.argv[1] for run in runs) else 1)
' "$RUN_ID"; then
  fail_verification "/runs does not list $RUN_ID — this API is serving a different run"
fi

if [[ "${1:-}" == "--api-only" ]]; then
  trap - EXIT
  echo
  echo "DARWINGUARD HISTORICAL DEMO READY"
  echo "Run: $RUN_ID"
  echo "Backend: http://127.0.0.1:$PORT"
  echo "Frontend: http://localhost:$FRONTEND_PORT"
  echo "Mode: HISTORICAL · READ ONLY"
  echo
  echo "API detached (pid $API_PID). Start the frontend with:"
  echo "  (cd \"$REPO_ROOT/frontend\" && npm run dev -- --port $FRONTEND_PORT --strictPort)"
  echo "Stop the API with: kill $API_PID"
  exit 0
fi

require_port_free "$FRONTEND_PORT" "the frontend must own :$FRONTEND_PORT"
echo
echo "DARWINGUARD HISTORICAL DEMO READY"
echo "Run: $RUN_ID"
echo "Backend: http://127.0.0.1:$PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Mode: HISTORICAL · READ ONLY"
echo
echo "starting frontend dev server (Ctrl-C tears down the API too)…"
cd "$REPO_ROOT/frontend"
npm run dev -- --port "$FRONTEND_PORT" --strictPort
