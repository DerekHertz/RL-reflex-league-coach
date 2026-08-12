from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from lolcoach.config import get_settings


@lru_cache
def get_anthropic() -> AsyncAnthropic:
    settings = get_settings()
    return AsyncAnthropic(api_key=settings.anthropic_api_key)
