"""NumberProvenanceGuard -- rejects any number in the LLM's response that
doesn't trace back to the fact sheet, plus rank-tier language and dangling
finding_id references.

This is the single highest-leverage anti-hallucination device in the
product: without it, one hallucinated stat destroys trust irrecoverably. On
violation the caller should attempt one repair, then fall back to
deterministic template text -- the product degrades to rule-engine output
rather than ever shipping an invented number.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

from lolcoach.analysis.factsheet import MatchFactSheet
from lolcoach.llm.schemas import CoachingResponse

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Deliberately excludes "gold" -- it's the game's own currency name and used
# constantly in legitimate coaching text ("you had a 700 gold lead"). Every
# other tier name is unambiguous in this context.
_FORBIDDEN_TERMS = re.compile(
    r"\b(iron|bronze|silver|platinum|emerald|diamond|master|grandmaster|challenger|mmr|elo)\b|\blp\b",
    re.IGNORECASE,
)


class GuardViolation(NamedTuple):
    field: str
    kind: Literal["unknown_number", "unknown_finding_id", "forbidden_term"]
    detail: str


def _collect_allowed_numbers(sheet: MatchFactSheet) -> set[str]:
    allowed: set[str] = {str(i) for i in range(0, 11)}  # small ordinals/ranks always OK

    def add(value: float | int | None) -> None:
        if value is None:
            return
        allowed.add(str(value))
        allowed.add(str(round(value)))
        allowed.add(str(int(value)))
        allowed.add(f"{value:.1f}")
        allowed.add(str(round(value, 1)))

    for m in sheet.metrics:
        add(m.value)
        for c in m.comparisons:
            add(c.peer_value)
            add(c.delta)
            add(c.rank_in_lobby)
    for f in sheet.findings:
        for e in f.evidence:
            add(e.value)
            add(e.peer_value)
        for ts in f.timestamps:
            allowed.add(ts)
            allowed.update(ts.split(":"))
    for c in sheet.clean_checks:
        for e in c.evidence:
            add(e.value)
            add(e.peer_value)
    for token in sheet.match.duration.split(":"):
        allowed.add(token)

    return allowed


class NumberProvenanceGuard:
    def __init__(self, sheet: MatchFactSheet) -> None:
        self._allowed_numbers = _collect_allowed_numbers(sheet)
        self._finding_ids = {f.id for f in sheet.findings}

    def check(self, response: CoachingResponse) -> list[GuardViolation]:
        violations: list[GuardViolation] = []

        for finding_id in response.focus_areas:
            if finding_id not in self._finding_ids:
                violations.append(GuardViolation("focus_areas", "unknown_finding_id", finding_id))
        for narration in response.narrations:
            if narration.finding_id not in self._finding_ids:
                violations.append(GuardViolation("narrations.finding_id", "unknown_finding_id", narration.finding_id))

        text_fields: list[tuple[str, str]] = [
            ("headline", response.headline),
            *(("what_went_well", t) for t in response.what_went_well),
            *(("narrations.explanation", n.explanation) for n in response.narrations),
            *(("narrations.fix", n.fix) for n in response.narrations),
            *(("narrations.drill", n.drill) for n in response.narrations if n.drill),
            ("closing", response.closing),
        ]

        for field, text in text_fields:
            violations.extend(self._check_text(field, text))

        return violations

    def _check_text(self, field: str, text: str) -> list[GuardViolation]:
        violations: list[GuardViolation] = []
        for match in _NUMBER_RE.finditer(text):
            token = match.group()
            if token not in self._allowed_numbers:
                violations.append(GuardViolation(field, "unknown_number", token))
        forbidden_match = _FORBIDDEN_TERMS.search(text)
        if forbidden_match:
            violations.append(GuardViolation(field, "forbidden_term", forbidden_match.group()))
        return violations
