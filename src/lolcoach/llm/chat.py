"""Answers a follow-up question about one already-analyzed match.

Same shape as narrator.py's call/repair/fallback flow, reusing the same
NumberProvenanceGuard state so a chat answer is held to the identical
anti-hallucination bar as the narration -- see guard.py's module docstring
for why that bar exists at all.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.llm.client import get_anthropic
from lolcoach.llm.guard import NumberProvenanceGuard, repair_note
from lolcoach.llm.prompts import SYSTEM_CHAT
from lolcoach.llm.schemas import ChatAnswer, ChatTurn, CoachingResponse

_MODEL = "claude-opus-5"
_MAX_TOKENS = 4000  # a chat answer is a few sentences, not a full report


def _user_message(sheet: MatchFactSheet, narrative: CoachingResponse, question: str, history: list[ChatTurn]) -> str:
    turns = "\n".join(f"<question>{t.question}</question>\n<answer>{t.answer}</answer>" for t in history)
    return (
        f"<fact_sheet>{sheet.model_dump_json()}</fact_sheet>\n\n"
        f"<coaching_report>{narrative.model_dump_json()}</coaching_report>\n\n"
        + (f"<conversation_so_far>\n{turns}\n</conversation_so_far>\n\n" if history else "")
        + f"<question>{question}</question>\n\n"
        "Answer this question as structured output."
    )


async def _call_claude(
    client: AsyncAnthropic,
    sheet: MatchFactSheet,
    narrative: CoachingResponse,
    question: str,
    history: list[ChatTurn],
    *,
    repair_instructions: str | None = None,
) -> ChatAnswer:
    content = _user_message(sheet, narrative, question, history)
    if repair_instructions:
        content += f"\n\n<repair_instructions>{repair_instructions}</repair_instructions>"

    response = await client.messages.parse(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_CHAT, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": content}],
        output_format=ChatAnswer,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError("Claude did not return a parsed structured output (refusal or schema mismatch)")
    return parsed


def _fallback_answer() -> ChatAnswer:
    return ChatAnswer(
        answer="I couldn't put together a reliable answer to that -- try rephrasing the question, or check the report above for what's already covered.",
        cited_finding_ids=[],
    )


async def answer_question(
    sheet: MatchFactSheet, narrative: CoachingResponse, question: str, history: list[ChatTurn]
) -> tuple[ChatAnswer, bool]:
    """Returns (answer, used_fallback), same guard-safe-by-construction
    guarantee as narrate_match: a validated Claude response, or -- after one
    failed repair attempt -- a static fallback that can't fail the guard.
    """
    client = get_anthropic()
    guard = NumberProvenanceGuard(sheet)

    response = await _call_claude(client, sheet, narrative, question, history)
    violations = guard.check_chat_answer(response)

    if violations:
        response = await _call_claude(
            client, sheet, narrative, question, history, repair_instructions=repair_note(violations)
        )
        violations = guard.check_chat_answer(response)

    if violations:
        return _fallback_answer(), True

    return response, False
