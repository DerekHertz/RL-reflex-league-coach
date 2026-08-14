"""Turns a MatchFactSheet into a CoachingResponse via Claude.

Whole-match, one call -- not per-finding. Per-finding calls can't see that
"won lane at 15" and "died repeatedly in the enemy jungle at 22" are the same
story, can't rank findings against each other, and cost N times the tokens.

On a guard violation: one repair attempt, then fall back to deterministic
template text. The product degrades to rule-engine output rather than ever
shipping a hallucinated number.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.llm.client import get_anthropic
from lolcoach.llm.guard import NumberProvenanceGuard, repair_note
from lolcoach.llm.prompts import SYSTEM_COACH
from lolcoach.llm.schemas import CoachingResponse, FindingNarration

MODEL = "claude-opus-5"  # public: service.py reports this as narration provenance
_MAX_TOKENS = 16000  # shared budget for thinking (on by default on Opus 5) + output

_SEVERITY_ORDER = {"info": 0, "minor": 1, "moderate": 2, "major": 3}

_FALLBACK_FIXES: dict[str, str] = {
    "unspent_gold": (
        "Buy something the moment you're back at base with enough gold for a meaningful item -- even a partial "
        "component -- instead of waiting to save up for a full item."
    ),
    "time_dead": (
        "Before fighting or diving, weigh the trade against what a death costs at this point in the game -- "
        "late-game deaths are far more expensive than early ones."
    ),
    "gold_curve_shape": (
        "After building an early lead, prioritize converting it into objectives (turrets, dragons) rather than "
        "continuing to farm alone -- leads decay if they aren't pressed."
    ),
}


def _user_message(sheet: MatchFactSheet) -> str:
    return (
        f"<fact_sheet>{sheet.model_dump_json()}</fact_sheet>\n\n"
        "Write the coaching response for this match as structured output."
    )


async def _call_claude(
    client: AsyncAnthropic, sheet: MatchFactSheet, *, repair_note: str | None = None
) -> CoachingResponse:
    content = _user_message(sheet)
    if repair_note:
        content += f"\n\n<repair_instructions>{repair_note}</repair_instructions>"

    response = await client.messages.parse(
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_COACH, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": content}],
        output_format=CoachingResponse,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError("Claude did not return a parsed structured output (refusal or schema mismatch)")
    return parsed


def _fallback_response(sheet: MatchFactSheet) -> CoachingResponse:
    top = sorted(sheet.findings, key=lambda f: _SEVERITY_ORDER[f.severity], reverse=True)[:3]
    narrations = [
        FindingNarration(
            finding_id=f.id,
            explanation=f.what_happened,
            fix=_FALLBACK_FIXES.get(f.id.split(":", 1)[0], "Review this finding and adjust your approach next game."),
        )
        for f in top
    ]
    headline = (
        f"{len(sheet.findings)} thing(s) to work on this game, starting with {top[0].title.lower()}."
        if top
        else "A clean game in the areas we checked."
    )
    return CoachingResponse(
        headline=headline,
        what_went_well=[c.title for c in sheet.clean_checks][:3],
        focus_areas=[f.id for f in top],
        narrations=narrations,
        closing="Generated summary unavailable this time -- showing the raw findings instead.",
    )


async def narrate_match(sheet: MatchFactSheet) -> tuple[CoachingResponse, bool]:
    """Returns (response, used_fallback). The returned response is always
    guard-safe: either a validated Claude response, or -- if Claude's first
    attempt and one repair attempt both failed validation -- the
    deterministic template fallback, which is guard-safe by construction.
    `used_fallback=True` tells the caller the narrative degraded so they can
    surface that in telemetry or the UI.
    """
    client = get_anthropic()
    guard = NumberProvenanceGuard(sheet)

    response = await _call_claude(client, sheet)
    violations = guard.check(response)

    if violations:
        response = await _call_claude(client, sheet, repair_note=repair_note(violations))
        violations = guard.check(response)

    if violations:
        return _fallback_response(sheet), True

    return response, False
