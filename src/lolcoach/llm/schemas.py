"""The structured-output shape Claude must return.

Structured output (not free text) so the UI can attach prose to the right
finding card without parsing, and so finding_id referential integrity is
machine-checkable by the guard.
"""

from __future__ import annotations

from pydantic import BaseModel


class FindingNarration(BaseModel):
    finding_id: str
    explanation: str
    fix: str
    drill: str | None = None


class CoachingResponse(BaseModel):
    headline: str
    what_went_well: list[str]
    focus_areas: list[str]
    narrations: list[FindingNarration]
    closing: str
