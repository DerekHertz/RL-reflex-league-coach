# lolcoach

A League of Legends post-game coach: fetches your recent matches from the Riot API,
runs rule-based detectors against the match/timeline data, and has Claude turn the
findings into coaching narrative. Benchmarks are peer-relative (you vs. the other 9
players in the same match) rather than against any external rank/tier data.

## Status

Shipped: Riot ID in, coaching narrative out (CLI + web), map-position detectors,
champion recommendations, a cross-match ledger (fired/total per detector across your
analyzed matches), a per-champion pool grid, and a stateless single-match chat panel
for asking follow-up questions about a report.

Web app pages: `/` (match report + chat), `/champions` (recommendations), `/ledger`,
`/pool`.

Not built yet: cross-match/persona coach chat (requirements parked in
`docs/chat-v2-cross-match-requirements.md`) and a Discord bot.

## Setup

Requires a [Riot dev API key](https://developer.riotgames.com/) (expires every 24h)
and an Anthropic API key.

```bash
cp .env.example .env   # fill in RIOT_API_KEY and ANTHROPIC_API_KEY
uv sync
```

## CLI

```bash
uv run lolcoach fetch "Player#NA1" --count 20     # populate the local match cache
uv run lolcoach analyze NA1_1234567890 --puuid <puuid> --detectors
uv run lolcoach narrate NA1_1234567890 --puuid <puuid>
uv run lolcoach serve                              # FastAPI on :8420
```

## Web app

```bash
uv run lolcoach serve          # backend, :8420
cd web && npm install && npm run dev   # frontend, :3000
```

## Tests

```bash
uv run pytest
```

No live API calls in the test suite -- detector/domain tests use synthetic
builders (`tests/builders.py`), and LLM guard tests (`tests/llm/test_guard.py`,
covering both match narration and chat answers) are offline. Live LLM calls
(narration, chat) are exercised manually, not in CI.

Frontend tests: `cd web && npm test`.
