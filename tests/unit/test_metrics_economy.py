from lolcoach.domain.timeline import TimelineIndex
from lolcoach.metrics.economy import cs_per_minute, gold_diff_at, gold_per_minute, total_gold_at
from tests.unit.factories import make_frame, make_participant, make_participant_frame, make_timeline


def test_total_gold_at_minute() -> None:
    frames = [
        make_frame(0, {1: make_participant_frame(1, total_gold=500)}),
        make_frame(600_000, {1: make_participant_frame(1, total_gold=6000)}),  # 10 min
    ]
    timeline = TimelineIndex(make_timeline(frames=frames))
    assert total_gold_at(timeline, 1, minute=10) == 6000
    assert total_gold_at(timeline, 1, minute=0) == 500


def test_gold_diff_at_positive_when_subject_ahead() -> None:
    frames = [
        make_frame(
            600_000,
            {
                1: make_participant_frame(1, total_gold=6500),
                6: make_participant_frame(6, total_gold=5800),
            },
        ),
    ]
    timeline = TimelineIndex(make_timeline(frames=frames))
    assert gold_diff_at(timeline, subject_id=1, opponent_id=6, minute=10) == 700


def test_gold_diff_at_none_when_frame_missing() -> None:
    timeline = TimelineIndex(make_timeline(frames=[]))
    assert gold_diff_at(timeline, subject_id=1, opponent_id=6, minute=10) is None


def test_gold_per_minute() -> None:
    p = make_participant(1, team_id=100, team_position="TOP", gold_earned=12000)
    from lolcoach.domain.match import ParticipantView

    view = ParticipantView(p)
    assert gold_per_minute(view, duration_s=1200.0) == 600.0  # 12000g / 20min


def test_cs_per_minute() -> None:
    p = make_participant(1, team_id=100, team_position="TOP", total_minions_killed=180, neutral_minions_killed=20)
    from lolcoach.domain.match import ParticipantView

    view = ParticipantView(p)
    assert cs_per_minute(view, duration_s=1200.0) == 10.0  # 200 cs / 20min


def test_zero_duration_does_not_divide_by_zero() -> None:
    from lolcoach.domain.match import ParticipantView

    view = ParticipantView(make_participant(1, team_id=100, team_position="TOP"))
    assert gold_per_minute(view, duration_s=0.0) == 0.0
    assert cs_per_minute(view, duration_s=0.0) == 0.0
