"""Gold/CS metrics -- facts, no judgement (judgement lives in detectors/)."""

from __future__ import annotations

from lolcoach.domain.match import ParticipantView
from lolcoach.domain.timeline import TimelineIndex


def total_gold_at(timeline: TimelineIndex, participant_id: int, minute: int) -> int | None:
    frame = timeline.frame_at_or_before(minute * 60_000)
    if frame is None:
        return None
    return frame.participant_frame(participant_id).total_gold


def gold_diff_at(
    timeline: TimelineIndex, subject_id: int, opponent_id: int, minute: int
) -> int | None:
    a = total_gold_at(timeline, subject_id, minute)
    b = total_gold_at(timeline, opponent_id, minute)
    if a is None or b is None:
        return None
    return a - b


def gold_per_minute(participant: ParticipantView, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return participant.gold_earned / (duration_s / 60.0)


def cs_per_minute(participant: ParticipantView, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return participant.total_cs / (duration_s / 60.0)


def unspent_gold_series(
    timeline: TimelineIndex, participant_id: int
) -> list[tuple[int, int]]:
    """[(timestamp_ms, currentGold), ...] across the game, for detecting
    "sitting on gold" runs.
    """
    return [
        (f.timestamp_ms, f.participant_frame(participant_id).current_gold)
        for f in timeline.frames
    ]
