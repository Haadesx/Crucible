#!/usr/bin/env bash
# VENUE-SHIPPING-SMOKE-20260926-125109 — dedicated JSON snapshot (Atlas auth rejected).
# Exact launch command, kept with the run for reproducibility.
set -euo pipefail
cd "$(dirname "$0")/../.."
RUN_ID=VENUE-SHIPPING-SMOKE-20260926-125109
exec env \
  DEV_STATE_PATH="experiments/$RUN_ID/state.json" \
  EXPORT_DIR="experiments/$RUN_ID/exports" \
  MONGODB_URI= TEST_MODE=false \
  .venv/bin/python -u -m app.coevolution \
    --generations 1 --run-id "$RUN_ID" \
    --red-versions 2 --attacks-per-version 1 --blue-candidates 1 --red-eval-attacks 1 \
    --mode real
