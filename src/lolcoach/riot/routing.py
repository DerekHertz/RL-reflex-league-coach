"""Riot platform/region routing.

Riot API endpoints live behind two different kinds of routing:

- "Platform" routing (na1.api.riotgames.com, euw1..., etc) is used by
  SUMMONER-V4, LEAGUE-V4, CHAMPION-MASTERY-V4.
- "Regional"/cluster routing (americas/asia/europe/sea.api.riotgames.com) is
  used by MATCH-V5 and ACCOUNT-V1.

A matchId is "{PLATFORM}_{gameId}" (e.g. "NA1_4567890123"), so the cluster
for a match-v5 call can always be derived from the match ID itself -- the
caller never needs to separately track or ask for a region.
"""

from enum import StrEnum


class Cluster(StrEnum):
    AMERICAS = "americas"
    ASIA = "asia"
    EUROPE = "europe"
    SEA = "sea"


class Platform(StrEnum):
    NA1 = "na1"
    BR1 = "br1"
    LA1 = "la1"
    LA2 = "la2"
    KR = "kr"
    JP1 = "jp1"
    EUN1 = "eun1"
    EUW1 = "euw1"
    ME1 = "me1"
    TR1 = "tr1"
    RU = "ru"
    OC1 = "oc1"
    SG2 = "sg2"
    TW2 = "tw2"
    VN2 = "vn2"
    PH2 = "ph2"
    TH2 = "th2"


_PLATFORM_TO_CLUSTER: dict[Platform, Cluster] = {
    Platform.NA1: Cluster.AMERICAS,
    Platform.BR1: Cluster.AMERICAS,
    Platform.LA1: Cluster.AMERICAS,
    Platform.LA2: Cluster.AMERICAS,
    Platform.KR: Cluster.ASIA,
    Platform.JP1: Cluster.ASIA,
    Platform.EUN1: Cluster.EUROPE,
    Platform.EUW1: Cluster.EUROPE,
    Platform.ME1: Cluster.EUROPE,
    Platform.TR1: Cluster.EUROPE,
    Platform.RU: Cluster.EUROPE,
    Platform.OC1: Cluster.SEA,
    Platform.SG2: Cluster.SEA,
    Platform.TW2: Cluster.SEA,
    Platform.VN2: Cluster.SEA,
    # Unverified in Riot's published mapping; SEA is the closest geographic
    # cluster and the strong community expectation.
    Platform.PH2: Cluster.SEA,
    Platform.TH2: Cluster.SEA,
}


def platform_to_cluster(platform: Platform) -> Cluster:
    return _PLATFORM_TO_CLUSTER[platform]


def cluster_for_match_id(match_id: str) -> Cluster:
    """Derive the regional cluster for a match-v5 call from the match ID's
    platform prefix, e.g. "NA1_4567890123" -> Cluster.AMERICAS.
    """
    prefix, _, rest = match_id.partition("_")
    if not rest:
        raise ValueError(f"malformed match id: {match_id!r}")
    try:
        platform = Platform(prefix.lower())
    except ValueError as e:
        raise ValueError(f"unknown platform prefix in match id: {match_id!r}") from e
    return platform_to_cluster(platform)
