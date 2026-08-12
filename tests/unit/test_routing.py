import pytest

from lolcoach.riot.routing import Cluster, Platform, cluster_for_match_id, platform_to_cluster


@pytest.mark.parametrize(
    ("match_id", "expected"),
    [
        ("NA1_4567890123", Cluster.AMERICAS),
        ("na1_4567890123", Cluster.AMERICAS),
        ("EUW1_1234567890", Cluster.EUROPE),
        ("KR_1234567890", Cluster.ASIA),
        ("OC1_1234567890", Cluster.SEA),
        ("ME1_1234567890", Cluster.EUROPE),
    ],
)
def test_cluster_for_match_id(match_id: str, expected: Cluster) -> None:
    assert cluster_for_match_id(match_id) == expected


def test_cluster_for_match_id_malformed() -> None:
    with pytest.raises(ValueError, match="malformed"):
        cluster_for_match_id("not-a-match-id")


def test_cluster_for_match_id_unknown_platform() -> None:
    with pytest.raises(ValueError, match="unknown platform"):
        cluster_for_match_id("XX9_123")


def test_every_platform_maps_to_a_cluster() -> None:
    for platform in Platform:
        assert platform_to_cluster(platform) in Cluster
