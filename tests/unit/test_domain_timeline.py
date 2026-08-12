from lolcoach.domain.timeline import TimelineIndex
from tests.unit.factories import make_frame, make_participant_frame, make_timeline


def test_participant_frame_indexed_by_string_key() -> None:
    # participantFrames is keyed by the STRING "1".."10", not an int -- this
    # test would fail if that indexing quirk regressed.
    frame = make_frame(0, {1: make_participant_frame(1, total_gold=500)})
    timeline = TimelineIndex(make_timeline(frames=[frame]))
    pf = timeline.frames[0].participant_frame(1)
    assert pf.total_gold == 500


def test_frame_at_or_before_picks_latest_frame_not_exceeding_timestamp() -> None:
    frames = [
        make_frame(0, {1: make_participant_frame(1, total_gold=500)}),
        make_frame(60_000, {1: make_participant_frame(1, total_gold=1000)}),
        make_frame(120_000, {1: make_participant_frame(1, total_gold=1500)}),
    ]
    timeline = TimelineIndex(make_timeline(frames=frames))

    assert timeline.frame_at_or_before(90_000).participant_frame(1).total_gold == 1000
    assert timeline.frame_at_or_before(0).participant_frame(1).total_gold == 500
    assert timeline.frame_at_or_before(-1) is None
    assert timeline.frame_at_or_before(999_999).participant_frame(1).total_gold == 1500


def test_cs_sums_lane_and_jungle_minions() -> None:
    pf = make_participant_frame(1, minions_killed=40, jungle_minions_killed=10)
    frame = make_frame(0, {1: pf})
    timeline = TimelineIndex(make_timeline(frames=[frame]))
    assert timeline.frames[0].participant_frame(1).cs == 50


def test_duplicate_skill_level_up_events_are_deduped() -> None:
    # Known live Riot bug (~patch 15.17+): exact-duplicate SKILL_LEVEL_UP
    # events with identical participantId/skillSlot/timestamp.
    dup_event = {"type": "SKILL_LEVEL_UP", "participantId": 1, "skillSlot": 1, "timestamp": 5000}
    frame = make_frame(0, {1: make_participant_frame(1)}, events=[dup_event, dict(dup_event)])
    timeline = TimelineIndex(make_timeline(frames=[frame]))
    skill_events = timeline.events_of_type("SKILL_LEVEL_UP")
    assert len(skill_events) == 1


def test_non_skill_level_up_events_are_never_deduped() -> None:
    # Two genuinely distinct CHAMPION_KILL events must both survive even if
    # some fields coincide.
    kill_a = {"type": "CHAMPION_KILL", "killerId": 1, "victimId": 6, "timestamp": 5000}
    kill_b = {"type": "CHAMPION_KILL", "killerId": 1, "victimId": 6, "timestamp": 5000}
    frame = make_frame(0, {1: make_participant_frame(1)}, events=[kill_a, kill_b])
    timeline = TimelineIndex(make_timeline(frames=[frame]))
    assert len(timeline.events_of_type("CHAMPION_KILL")) == 2


def test_events_are_time_sorted_across_frames() -> None:
    late_event = {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 90_000}
    early_event = {"type": "WARD_PLACED", "creatorId": 1, "timestamp": 10_000}
    frames = [
        make_frame(0, {1: make_participant_frame(1)}, events=[late_event]),
        make_frame(60_000, {1: make_participant_frame(1)}, events=[early_event]),
    ]
    timeline = TimelineIndex(make_timeline(frames=frames))
    timestamps = [e["timestamp"] for e in timeline.events]
    assert timestamps == sorted(timestamps)


def test_level_at_uses_level_up_events_not_frame_sampling() -> None:
    level_up_6 = {"type": "LEVEL_UP", "participantId": 1, "level": 6, "timestamp": 8 * 60_000}
    frame = make_frame(0, {1: make_participant_frame(1, level=1)}, events=[level_up_6])
    timeline = TimelineIndex(make_timeline(frames=[frame]))
    assert timeline.level_at(1, 8 * 60_000) == 6
    assert timeline.level_at(1, 0) == 1
