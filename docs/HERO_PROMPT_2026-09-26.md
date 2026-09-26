# Crucible — Hero Demo Prompt (2026-09-26)

Paste the prompt below into the hero terminal. It is self-contained: frozen HEAD
`b49a0f6`, exact commands, expected UI states, and hard rules.

````text
You are the DEMO OPERATOR ("hero") for Crucible at the MongoDB hackathon. Everything is frozen and rehearsed.

REPO: /Volumes/Auxilary/Side_Projects/HackMongo
HEAD: b49a0f6 "fix: make DarwinGuard demo UI truthful and safe" (do not change code, do not commit, do not touch historical evidence)
CURRENTLY RUNNING: Atlas observer on http://127.0.0.1:8000 (pid 90736) and frontend on http://localhost:5175 (pid 87149).

GOAL: run the exact demo flow below for judges, in order. Do not improvise features, models, or numbers.

DEMO FLOW

1) LONG-HORIZON RUN — ~3 hours (historical, read-only)
   - Stop the Atlas observer first: lsof -ti tcp:8000 | xargs kill
   - Run: scripts/demo-overnight.sh --api-only
     (it refuses to start if :8000 is busy and prints the owning PID — trust it; it also verifies the run id and read-only state before printing DARWINGUARD HISTORICAL DEMO READY)
   - Open http://localhost:5175, stay on VERSIONS and press FIT. The first window is RED × BLUE ACROSS GENERATIONS for OVERNIGHT-COEV-20260926-022643: ASR 0.667 in G00 then 0 for G01–G06, Red mean fitness moving per generation, and each generation's red +promoted / −rejected mutations.
   - Point out the top-bar chip: HISTORICAL · READ ONLY, footer: MODEL WEIGHTS FROZEN · HARNESS EVOLVES.
   - Select G00. Open the RED AGENT window (model, strategy, fitness). Follow "generated" to a DIRECT OVERRIDE attack marked BREACH and show the injected content.
   - Follow "execute" to SANDBOX: stage trace, Tool permission gate FAIL, 1 executed / 8 proposed.
   - Follow "evidence" to EVALUATOR · BREACH, then "breach" to BLUE ENGINEER.
   - In BLUE ENGINEER say: historical patches were authored by Ling (inclusionai/ling-3.0-flash-fin:free). Current shipping primary is Nemotron; history keeps its original attribution.
   - Open HARNESS PATCH: parent, operations, validation, author. Say: "The model weights stay frozen. What evolves is the harness."
   - Open CANDIDATE, then REPLAY / JUDGE: fitness 0.702, block rate 1.0, 10 battles, PROMOTED. Then CHAMPION.
   - Click G01–G06: ASR stays 0.0 while Red keeps mutating; use RED EVO to show promoted and rejected mutations with measured fitness.
   - Switch to LINEAGE: Red and Blue ancestry, promoted/rejected branches.
   - Do not touch the START controls — they are intentionally disabled; live runs start from the CLI.

2) TWO-SIDED (historical, read-only)
   - Stop the long-horizon API: lsof -ti tcp:8000 | xargs kill
   - Run: scripts/demo-two-sided.sh --api-only
   - Open the new run COEV-SEL-20260926-011123 and show ASR 0.0 → 0.333 → 0.667 → 0.0.
   - Explain: Blue holds, Red adapts and breaks through, Blue answers and holds again — adaptive pressure in both directions. Never mix these numbers with the long-horizon run.

3) ATLAS LIVE
   - Stop the two-sided API: lsof -ti tcp:8000 | xargs kill
   - Restart the Atlas observer from backend/ with the .env URI:
     cd backend && RUN_MODE=DEV TEST_MODE=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   - Open http://localhost:5175. Chip must read LIVE · ATLAS CONNECTED. Latest complete live run: CRUCIBLE-LIVE-20260926-162014 (ASR [1.0, 0.0]).
   - Open the BLUE ENGINEER window and the HARNESS PATCH author row: nvidia/nemotron-3-super-120b-a12b:free; the promoted patch set recipient_validation + input_classifier, fitness 0.676.
   - Open ATLAS MEMORY: 5 recalls, outcomes PROMOTED ×3 / REJECTED ×1. Say: "Security alone doesn't win — a defense has to preserve useful behavior."
   - For the rejection story, open the persisted event run DARWINGUARD-EVENT-20260926: REPLAY / JUDGE REJECTED — "utility fell from 0.62 to 0.50".

OPTIONAL LIVE GENERATION (only if judges want to see one):
   cd backend && RUN_MODE=REAL PERSISTENCE=atlas .venv/bin/python -u -m app.coevolution --mode real --generations 1 --red-versions 1 --attacks-per-version 1 --red-eval-attacks 1 --blue-candidates 1 --baseline naked --run-id DARWINGUARD-EVENT-$(date +%H%M%S)
   Then press ⟳ in the UI. Takes 3–6 minutes; do not start this if time is short.

JUDGE STORY (60–90 seconds): Red is an attacker model that writes prompt-injection and tool-output attacks; Blue is the defender — a fast executor answers tool calls under the harness, and an engineer model reads failures and writes a small HarnessPatch. Every attack runs in a deterministic sandbox and is scored on security and task utility; Red mutations and Blue patches are promoted only on measured comparisons, and losers are persisted as rejections. That is why this is evolution, not two chatbots talking. The ~3-hour long-horizon run (7 generations, 256 model calls, 2h42m wall clock) shows two real breaches, a promoted patch, then six generations where it holds while Red keeps mutating; the two-sided run shows both sides adapting; Atlas persists the live runs and a fresh process can rebuild them.

HARD RULES: no code changes, no commits, no model/config changes; never point the historical demos at Atlas; never modify backend/experiments/**; frontend is :5175 (NOT :5173, that's another project); if a script exits complaining about :8000, free the port as it instructs and re-run.

WHEN DONE: report which segments ran, exact commands, the chip/run/ASR/attribution you saw, and any deviation from expected output.
````
