# Coach chat v2: cross-match requirements (deferred, not scoped for build)

v1 chat (grounded Q&A on a single match's fact sheet + narration) is the only chat scope currently approved for implementation. This doc parks the cross-match/persona scope raised during the 2026-08-14 grilling session so it isn't lost, and marks it as a hard dependency on the ledger and pool-grid features.

## Functional requirements

1. Answer questions grounded in aggregate history, not just the current match (e.g. "am I always low on wards?") — sourced from the ledger's fire-rate data, not the single-match fact sheet.
2. Support multi-turn conversation. The current SSE job model (`src/lolcoach/jobs/runner.py`) is one-shot, server→client, terminates on `done`/`error` — it cannot take a new client message mid-stream.
3. Persona voice selection (mockups named Archivist/Ironquill/Wren; names don't survive anywhere in committed code — only `web/app/typography.css:1`'s "Ionian Parchment" comment remains). Needs its own grilling round before build: single default voice vs. persona switcher, and whether personas differ in tone only or in what context each is grounded on.
4. Chat history persistence: session-only (ephemeral) vs. SQLite-backed and tied to a player/analysis-run. Open.
5. Hard dependency: cannot ship before the ledger (and likely pool-grid) exist and are queryable, since this is what cross-match grounding reads from.

## Non-functional requirements

1. **Anonymization boundary**: ledger/aggregate stats fed to the LLM must be reshaped into the same identity-free schema class as `MatchFactSheet` before reaching `lolcoach.llm` — enforced today by `tests/contract/test_llm_boundary.py`'s import-graph walk. No new raw-data import path into `llm/` is acceptable.
2. **Transport**: needs a new streaming/session mechanism distinct from `JobRunner` (in-memory, single-process, job lost on restart per `jobs/runner.py:1-7`) — a multi-turn chat session needs its own persistence/liveness story.
3. **Prompt cost/token budget**: cross-match grounding could pull large aggregates across many cached matches — needs an explicit cap on how much history feeds one prompt.
4. **No fabricated data**: same standing rule as the rest of the project — grounding must come from real cached/computed data (ledger, fact sheets), never inferred or hallucinated aggregate stats.

## Explicitly out of scope for this doc

Implementation plan, UI mockups beyond what's already lost from the original design spec, and the persona grilling round — all deferred until v1 chat and the ledger are shipped.
