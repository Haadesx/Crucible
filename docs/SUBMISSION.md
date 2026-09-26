# Crucible — Submission Description

Crucible evolves an AI agent's security harness under continuous adversarial pressure —
blocking new attacks without breaking legitimate tasks. A Red attacker running on a local
GPU rig generates prompt-injection and tool-manipulation attacks against the agent's
runtime harness. Every attack executes in a deterministic sandbox and is scored by an
evaluator. When an attack breaches, Crucible queries MongoDB Atlas Vector Search for
similar failures from earlier runs — including how those earlier patches turned out — and
feeds that memory to a Blue engineer model, which proposes an executable HarnessPatch. The
candidate is then replayed against both malicious attacks and benign tasks; only a
candidate that beats the champion's fitness while keeping benign utility above a 0.50
floor and within 0.10 of the champion is promoted, and rejections
stay on record. Model weights stay frozen: the harness and the attack strategy are what
evolve. Atlas persists the whole lineage — versions, episodes, model calls, patches,
memories and champions — so every claim is inspectable.
