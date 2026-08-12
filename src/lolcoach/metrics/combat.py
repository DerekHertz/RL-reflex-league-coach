"""Combat/death metrics -- facts, no judgement."""

from __future__ import annotations

# Base Respawn Wait by level 1-18, in seconds. Post-patch-14.16 values.
_BRW_BY_LEVEL: tuple[float, ...] = (
    10, 10, 12, 12, 14, 16, 20, 25, 28, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5,
)


def base_respawn_wait_s(level: int) -> float:
    level = max(1, min(18, level))
    return _BRW_BY_LEVEL[level - 1]


def time_increase_factor(death_time_s: float) -> float:
    """Death-timer scaling factor. Riot documents only two fixed points --
    0% before 15:00, capped at +50% by 55:00 -- and has never published the
    exact stepped bracket increments in between (they're patch-sensitive).
    This linear ramp between the two documented points is a defensible
    approximation for RELATIVE severity weighting within a single match; it
    is not used for exact death-timer prediction.
    """
    minute = death_time_s / 60.0
    if minute <= 15.0:
        return 0.0
    if minute >= 55.0:
        return 0.5
    return 0.5 * (minute - 15.0) / 40.0


def death_cost_s(level: int, death_time_s: float) -> float:
    return base_respawn_wait_s(level) * (1.0 + time_increase_factor(death_time_s))


def time_dead_share(total_time_spent_dead_s: float, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return total_time_spent_dead_s / duration_s
