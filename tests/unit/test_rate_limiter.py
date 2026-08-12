import asyncio
import time

import pytest

from lolcoach.riot.rate_limiter import HeaderAwareLimiter, _parse_limit_header


def test_parse_limit_header() -> None:
    assert _parse_limit_header("20:1,100:120") == [(20, 1.0), (100, 120.0)]
    assert _parse_limit_header("") == []
    assert _parse_limit_header("1:1") == [(1, 1.0)]


@pytest.mark.asyncio
async def test_acquire_allows_up_to_margin_adjusted_limit() -> None:
    # 20 req/1s default, 0.9 margin -> 18 immediate acquires, 19th should wait.
    limiter = HeaderAwareLimiter(safety_margin=0.9)
    for _ in range(18):
        await asyncio.wait_for(limiter.acquire("americas", "test-method"), timeout=0.1)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("americas", "test-method"), timeout=0.05)


@pytest.mark.asyncio
async def test_penalize_blocks_until_retry_after() -> None:
    limiter = HeaderAwareLimiter()
    await limiter.penalize("americas", "test-method", retry_after_s=0.15)

    start = time.monotonic()
    await limiter.acquire("americas", "test-method")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_penalize_service_wide_blocks_all_methods_in_region() -> None:
    limiter = HeaderAwareLimiter()
    await limiter.penalize("americas", "some-method", retry_after_s=0.15, service_wide=True)

    start = time.monotonic()
    await limiter.acquire("americas", "totally-different-method")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1


def test_observe_reconciles_higher_server_reported_usage() -> None:
    limiter = HeaderAwareLimiter(safety_margin=1.0)
    headers = {
        "x-app-rate-limit": "20:1,100:120",
        "x-app-rate-limit-count": "19:1,50:120",
    }
    limiter.observe("americas", "test-method", headers)
    bucket = limiter._app("americas")[0]
    assert len(bucket.timestamps) == 19
