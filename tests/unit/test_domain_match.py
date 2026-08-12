import pytest

from lolcoach.domain.match import MatchView, normalize_duration_s
from tests.unit.factories import make_match, make_participant


def test_normalize_duration_seconds_when_end_timestamp_present() -> None:
    info = {"gameDuration": 1620, "gameEndTimestamp": 1_700_000_000_000}
    assert normalize_duration_s(info) == 1620.0


def test_normalize_duration_milliseconds_when_end_timestamp_absent() -> None:
    # Pre-patch-11.20 matches: gameDuration is ms, gameEndTimestamp is absent.
    info = {"gameDuration": 1_620_000}
    assert normalize_duration_s(info) == 1620.0


def test_match_view_basic_fields() -> None:
    match = MatchView(make_match())
    assert match.match_id == "NA1_4567890123"
    assert match.queue_id == 420
    assert match.duration_s == 1620.0
    assert len(match.participants) == 10


def test_participant_view_total_cs_sums_lane_and_neutral() -> None:
    p = make_participant(1, team_id=100, team_position="TOP", total_minions_killed=150, neutral_minions_killed=20)
    match = MatchView(make_match(participants=[p]))
    view = match.participants[0]
    assert view.total_cs == 170


def test_participant_by_puuid_not_found_raises() -> None:
    match = MatchView(make_match())
    with pytest.raises(KeyError):
        match.participant_by_puuid("does-not-exist")


def test_peer_group_lane_opponent_matched_by_team_position() -> None:
    match = MatchView(make_match())
    subject = match.participant_by_puuid("PUUID_01")  # team 100, TOP
    peers = match.peer_group(subject)
    assert peers.lane_opponent is not None
    assert peers.lane_opponent.team_position == "TOP"
    assert peers.lane_opponent.team_id == 200
    assert peers.lane_opponent.puuid != subject.puuid


def test_peer_group_role_cohort_excludes_subject() -> None:
    match = MatchView(make_match())
    subject = match.participant_by_puuid("PUUID_03")  # MIDDLE
    peers = match.peer_group(subject)
    assert len(peers.role_cohort) == 1  # the other MIDDLE player
    assert all(p.puuid != subject.puuid for p in peers.role_cohort)


def test_peer_group_no_lane_opponent_when_team_position_empty() -> None:
    participants = [
        make_participant(1, team_id=100, team_position="", puuid="A"),
        make_participant(2, team_id=200, team_position="", puuid="B"),
    ]
    match = MatchView(make_match(participants=participants))
    subject = match.participant_by_puuid("A")
    peers = match.peer_group(subject)
    assert peers.lane_opponent is None
    assert peers.role_cohort == ()


def test_rank_in_lobby_higher_is_better() -> None:
    participants = [
        make_participant(i + 1, team_id=100 if i < 5 else 200, team_position=pos, gold_earned=10000 + i * 100, puuid=f"P{i}")
        for i, pos in enumerate(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] * 2)
    ]
    match = MatchView(make_match(participants=participants))
    # P9 has the highest gold_earned (10000 + 900), so should rank 1st.
    subject = match.participant_by_puuid("P9")
    peers = match.peer_group(subject)
    rank = peers.rank_in_lobby(lambda p: p.gold_earned, higher_is_better=True)
    assert rank == 1

    subject_low = match.participant_by_puuid("P0")
    peers_low = match.peer_group(subject_low)
    rank_low = peers_low.rank_in_lobby(lambda p: p.gold_earned, higher_is_better=True)
    assert rank_low == 10


def test_compare_returns_none_peer_value_when_no_lane_opponent() -> None:
    participants = [make_participant(1, team_id=100, team_position="", puuid="A")]
    match = MatchView(make_match(participants=participants))
    subject = match.participant_by_puuid("A")
    peers = match.peer_group(subject)
    cmp = peers.compare(lambda p: p.gold_earned, higher_is_better=True, peer="lane_opponent")
    assert cmp.peer_value is None
    assert cmp.delta is None
