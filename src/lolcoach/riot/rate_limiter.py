"""Header-aware rate limiter for the Riot API.

A dev key allows 20 requests/second and 100 requests/2 minutes, expires every
24h, and burning it out for two minutes (a 429 storm) is far more costly than
being slightly conservative. This limiter:

- Enforces sliding-window buckets seeded from the documented dev-key defaults.
- Reconciles against the X-App-Rate-Limit-Count / X-Method-Rate-Limit-Count
  response headers, so if another process is sharing this key we notice and
  back off rather than only trusting our own bookkeeping.
- Honors Retry-After on a 429 by blocking the relevant bucket group.

Deliberately conservative: targets ~90% of the stated limit rather than 100%.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field


def _parse_limit_header(value: str) -> list[tuple[int, float]]:
    """Parse "20:1,100:120" -> [(20, 1.0), (100, 120.0)]."""
    pairs: list[tuple[int, float]] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        count_s, _, window_s = part.partition(":")
        pairs.append((int(count_s), float(window_s)))
    return pairs


@dataclass
class _Bucket:
    limit: int
    window_s: float
    timestamps: deque[float] = field(default_factory=deque)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_s
        while self.timestamps and self.timestamps[0] <= cutoff:
            self.timestamps.popleft()

    def wait_time(self, now: float) -> float:
        self._prune(now)
        if len(self.timestamps) < self.limit:
            return 0.0
        return max(0.0, self.timestamps[0] + self.window_s - now)

    def record(self, now: float) -> None:
        self.timestamps.append(now)

    def observed_count(self, reported_count: int, now: float) -> None:
        """Pad local tracking up to a server-reported count for this window,
        so we notice usage from other processes sharing the same key.
        """
        self._prune(now)
        while len(self.timestamps) < reported_count:
            self.timestamps.append(now)


class HeaderAwareLimiter:
    DEFAULT_APP_LIMITS: tuple[tuple[int, float], ...] = ((20, 1.0), (100, 120.0))

    def __init__(self, safety_margin: float = 0.9) -> None:
        self._safety_margin = safety_margin
        self._app_buckets: dict[str, list[_Bucket]] = {}
        self._method_buckets: dict[tuple[str, str], list[_Bucket]] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _with_margin(self, limit: int) -> int:
        return max(1, int(limit * self._safety_margin))

    def _app(self, region: str) -> list[_Bucket]:
        return self._app_buckets.setdefault(
            region,
            [_Bucket(limit=self._with_margin(limit), window_s=window) for limit, window in self.DEFAULT_APP_LIMITS],
        )

    def _method(self, region: str, method: str) -> list[_Bucket]:
        return self._method_buckets.setdefault((region, method), [])

    async def acquire(self, region: str, method: str) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                block_key = f"{region}:{method}"
                waits = [
                    self._blocked_until.get(region, 0.0) - now,
                    self._blocked_until.get(block_key, 0.0) - now,
                    *(b.wait_time(now) for b in self._app(region)),
                    *(b.wait_time(now) for b in self._method(region, method)),
                ]
                wait = max(waits)
                if wait <= 0:
                    for b in self._app(region):
                        b.record(now)
                    for b in self._method(region, method):
                        b.record(now)
                    return
                await asyncio.sleep(wait)

    def observe(self, region: str, method: str, headers: Mapping[str, str]) -> None:
        """Reconcile local bucket state against Riot's rate-limit headers."""
        now = time.monotonic()
        self._reconcile(self._app(region), headers, "x-app-rate-limit", "x-app-rate-limit-count", now)

        method_key = (region, method)
        limit_hdr = headers.get("x-method-rate-limit")
        if limit_hdr and not self._method_buckets.get(method_key):
            self._method_buckets[method_key] = [
                _Bucket(limit=self._with_margin(limit), window_s=window)
                for limit, window in _parse_limit_header(limit_hdr)
            ]
        self._reconcile(self._method(region, method), headers, "x-method-rate-limit", "x-method-rate-limit-count", now)

    @staticmethod
    def _reconcile(
        buckets: list[_Bucket],
        headers: Mapping[str, str],
        limit_header: str,
        count_header: str,
        now: float,
    ) -> None:
        count_hdr = headers.get(count_header)
        if not count_hdr or not buckets:
            return
        reported = dict(_parse_limit_header(count_hdr))  # {window: count}... but header is count:window
        # _parse_limit_header returns (count, window) tuples for count headers.
        for count, window in _parse_limit_header(count_hdr):
            for bucket in buckets:
                if abs(bucket.window_s - window) < 0.5:
                    bucket.observed_count(count, now)

    async def penalize(self, region: str, method: str, retry_after_s: float, *, service_wide: bool = False) -> None:
        async with self._lock:
            until = time.monotonic() + retry_after_s
            key = region if service_wide else f"{region}:{method}"
            self._blocked_until[key] = max(self._blocked_until.get(key, 0.0), until)
