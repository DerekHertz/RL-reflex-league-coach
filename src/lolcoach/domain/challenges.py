"""Wrapper around a participant's `challenges` object.

`challenges` is an undocumented, unstable Riot API extra (Riot devrel #801,
#754 -- questions unanswered for over a year). It provides ~150 precomputed
metrics (killParticipation, damagePerMinute, laneMinionsFirst10Minutes, ...)
but:

  - Fields are OMITTED when inapplicable/zero, not set to 0.
  - The whole object is absent on old-patch and non-SR (ARAM/Arena) matches.
  - Numeric types drift between int and float across patches.

This is the ONLY place `.get()` on `challenges` should ever be called --
every other module reads through this wrapper.
"""

from __future__ import annotations

from typing import Any


class Challenges:
    __slots__ = ("_raw",)

    def __init__(self, raw: dict[str, Any] | None) -> None:
        self._raw = raw or {}

    def __contains__(self, key: str) -> bool:
        return key in self._raw

    @property
    def is_present(self) -> bool:
        return bool(self._raw)

    def get(self, key: str, default: float | None = None) -> float | None:
        value = self._raw.get(key, default)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_int(self, key: str, default: int | None = None) -> int | None:
        value = self.get(key, None)
        return int(value) if value is not None else default
