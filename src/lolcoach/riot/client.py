"""Async Riot API client.

Only ACCOUNT-V1's by-riot-id lookup needs a caller-chosen cluster (and any of
americas/asia/europe works -- the account service is global). Everything
downstream is derived: by-puuid gives the platform, the platform gives the
match-v5 cluster, and match IDs carry their own platform prefix. So the
caller never has to track or guess a region for match data.

Match and timeline responses are cached forever (see cache.py) and never
touch the rate limiter on a cache hit -- this is what makes iterating on
detectors free after the first fetch.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import httpx

from lolcoach.riot.cache import RawCache
from lolcoach.riot.errors import RiotApiError, RiotNotFoundError
from lolcoach.riot.models import Account, MatchId, PlayerRef
from lolcoach.riot.rate_limiter import HeaderAwareLimiter
from lolcoach.riot.routing import Cluster, Platform, cluster_for_match_id, platform_to_cluster

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5


class RiotClient:
    def __init__(
        self,
        api_key: str,
        limiter: HeaderAwareLimiter,
        cache: RawCache,
        http: httpx.AsyncClient,
    ) -> None:
        self._api_key = api_key
        self._limiter = limiter
        self._cache = cache
        self._http = http
        self.request_count = 0
        self.throttled_count = 0

    async def _get(self, region: str, method: str, path: str, params: dict | None = None) -> dict | list:
        url = f"https://{region}.api.riotgames.com{path}"
        for attempt in range(_MAX_RETRIES):
            await self._limiter.acquire(region, method)
            self.request_count += 1
            resp = await self._http.get(url, params=params, headers={"X-Riot-Token": self._api_key})
            self._limiter.observe(region, method, resp.headers)

            if resp.status_code == 429:
                self.throttled_count += 1
                retry_after = float(resp.headers.get("retry-after", "1"))
                service_wide = "x-rate-limit-type" not in resp.headers
                logger.warning(
                    "429 from Riot API (%s %s), retry-after=%.1fs, service_wide=%s",
                    region,
                    method,
                    retry_after,
                    service_wide,
                )
                await self._limiter.penalize(region, method, retry_after, service_wide=service_wide)
                continue

            if resp.status_code == 404:
                raise RiotNotFoundError(404, resp.text)
            if resp.status_code >= 400:
                raise RiotApiError(resp.status_code, resp.text)

            return resp.json()

        raise RiotApiError(429, f"exceeded {_MAX_RETRIES} retries against {region}:{method}")

    async def account_by_riot_id(
        self, game_name: str, tag_line: str, cluster: Cluster = Cluster.AMERICAS
    ) -> Account:
        data = await self._get(
            cluster.value,
            "account-by-riot-id",
            f"/riot/account/v1/accounts/by-riot-id/{quote(game_name, safe='')}/{quote(tag_line, safe='')}",
        )
        assert isinstance(data, dict)
        return Account(puuid=data["puuid"], game_name=data.get("gameName", game_name), tag_line=data.get("tagLine", tag_line))

    async def platform_for_puuid(self, puuid: str, cluster: Cluster = Cluster.AMERICAS) -> Platform:
        data = await self._get(
            cluster.value,
            "account-region-by-game",
            f"/riot/account/v1/region/by-game/lol/by-puuid/{puuid}",
        )
        assert isinstance(data, dict)
        return Platform(data["region"].lower())

    async def match_ids(
        self,
        puuid: str,
        cluster: Cluster,
        *,
        count: int = 20,
        start: int = 0,
        queue: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[MatchId]:
        params: dict[str, int] = {"start": start, "count": min(count, 100)}
        if queue is not None:
            params["queue"] = queue
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        data = await self._get(
            cluster.value,
            "match-ids-by-puuid",
            f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
            params=params,
        )
        assert isinstance(data, list)
        return [MatchId(m) for m in data]

    async def match(self, match_id: MatchId) -> dict:
        cached = self._cache.get("match", match_id)
        if cached is not None:
            return cached
        cluster = cluster_for_match_id(match_id)
        data = await self._get(cluster.value, "match-by-id", f"/lol/match/v5/matches/{match_id}")
        assert isinstance(data, dict)
        self._cache.put("match", match_id, data)
        return data

    async def timeline(self, match_id: MatchId) -> dict:
        cached = self._cache.get("timeline", match_id)
        if cached is not None:
            return cached
        cluster = cluster_for_match_id(match_id)
        data = await self._get(cluster.value, "match-timeline", f"/lol/match/v5/matches/{match_id}/timeline")
        assert isinstance(data, dict)
        self._cache.put("timeline", match_id, data)
        return data

    async def match_and_timeline(self, match_id: MatchId) -> tuple[dict, dict]:
        match, timeline = await asyncio.gather(self.match(match_id), self.timeline(match_id))
        return match, timeline

    async def resolve_player(self, riot_id: str) -> PlayerRef:
        """Resolve "gameName#tagLine" -> puuid + platform + cluster.

        3-request worst case (account lookup + region lookup); callers should
        cache the result (see storage.player) so repeat lookups are free.
        """
        game_name, _, tag_line = riot_id.partition("#")
        if not tag_line:
            raise ValueError(f"expected 'gameName#tagLine', got {riot_id!r}")
        account = await self.account_by_riot_id(game_name, tag_line)
        platform = await self.platform_for_puuid(account.puuid)
        cluster = platform_to_cluster(platform)
        return PlayerRef(
            puuid=account.puuid,
            game_name=account.game_name,
            tag_line=account.tag_line,
            platform=platform,
            cluster=cluster,
        )
