from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from lolcoach.riot.routing import Cluster, Platform

MatchId = NewType("MatchId", str)


@dataclass(frozen=True, slots=True)
class Account:
    puuid: str
    game_name: str
    tag_line: str


@dataclass(frozen=True, slots=True)
class PlayerRef:
    puuid: str
    game_name: str
    tag_line: str
    platform: Platform
    cluster: Cluster
