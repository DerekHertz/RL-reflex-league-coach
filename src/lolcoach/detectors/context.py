"""The single argument every detector receives."""

from __future__ import annotations

from dataclasses import dataclass

from lolcoach.domain.match import MatchView, ParticipantView, PeerGroup
from lolcoach.domain.timeline import TimelineIndex


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    match: MatchView
    timeline: TimelineIndex | None
    subject: ParticipantView
    peers: PeerGroup

    def challenge(self, key: str, default: float | None = None) -> float | None:
        return self.subject.challenges.get(key, default)

    @classmethod
    def build(cls, match: MatchView, timeline: TimelineIndex | None, subject_puuid: str) -> AnalysisContext:
        subject = match.participant_by_puuid(subject_puuid)
        peers = match.peer_group(subject)
        return cls(match=match, timeline=timeline, subject=subject, peers=peers)
