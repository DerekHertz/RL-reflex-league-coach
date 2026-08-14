from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from lolcoach.playstyle.archetypes import (
    DEFAULT_ARCHETYPES_PATH,
    MIN_CHAMPIONS_PER_ROLE,
    VALID_ROLES,
    load_archetypes,
)

_VALID_AXES = {
    "aggression": 0.5,
    "farming": 0.5,
    "vision": 0.5,
    "objective_focus": 0.5,
    "risk_tolerance": 0.5,
    "teamfight_vs_split": 0.5,
}
_VALID_SALIENCE = {
    "aggression": 1.0,
    "farming": 0.5,
    "vision": 0.5,
    "objective_focus": 0.5,
    "risk_tolerance": 0.5,
    "teamfight_vs_split": 0.5,
}


def _entry(name: str, roles: list[str], **overrides) -> dict:
    entry = {
        "name": name,
        "roles": roles,
        "axes": dict(_VALID_AXES),
        "salience": dict(_VALID_SALIENCE),
        "identity": f"{name} test identity",
    }
    entry.update(overrides)
    return entry


def test_real_data_file_loads_and_validates() -> None:
    archetypes = load_archetypes(DEFAULT_ARCHETYPES_PATH)
    assert len(archetypes) >= 30
    names = [a.name for a in archetypes]
    assert len(names) == len(set(names))  # no duplicates


def test_real_data_file_covers_every_role_with_minimum_champions() -> None:
    archetypes = load_archetypes(DEFAULT_ARCHETYPES_PATH)
    counts = {role: 0 for role in VALID_ROLES}
    for a in archetypes:
        for role in a.roles:
            counts[role] += 1
    for role in VALID_ROLES:
        assert counts[role] >= MIN_CHAMPIONS_PER_ROLE, f"{role} has only {counts[role]} champions"


def test_real_data_file_axis_and_salience_values_in_bounds() -> None:
    archetypes = load_archetypes(DEFAULT_ARCHETYPES_PATH)
    for a in archetypes:
        for axis in _VALID_AXES:
            value = getattr(a.axes, axis)
            assert 0.0 <= value <= 1.0, f"{a.name}.{axis} axis value {value} out of [0,1]"
            salience = getattr(a.salience, axis)
            assert salience >= 0.0, f"{a.name}.{axis} salience {salience} is negative"


def test_valid_synthetic_roster_loads(tmp_path: Path) -> None:
    entries = []
    counter = 0
    for role in VALID_ROLES:
        for _ in range(MIN_CHAMPIONS_PER_ROLE):
            entries.append(_entry(f"Champ{counter}", [role]))
            counter += 1
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    archetypes = load_archetypes(path)
    assert len(archetypes) == len(entries)


def test_axis_value_out_of_range_raises(tmp_path: Path) -> None:
    entries = [_entry("BadAxis", ["TOP"], axes={**_VALID_AXES, "aggression": 1.5})]
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValidationError):
        load_archetypes(path)


def test_negative_axis_value_raises(tmp_path: Path) -> None:
    entries = [_entry("BadAxis", ["TOP"], axes={**_VALID_AXES, "vision": -0.1})]
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValidationError):
        load_archetypes(path)


def test_negative_salience_raises(tmp_path: Path) -> None:
    entries = [_entry("BadSalience", ["TOP"], salience={**_VALID_SALIENCE, "aggression": -1.0})]
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValidationError):
        load_archetypes(path)


def test_invalid_role_raises(tmp_path: Path) -> None:
    entries = [_entry("BadRole", ["CARRY"])]  # not a valid team position
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValidationError):
        load_archetypes(path)


def test_role_with_too_few_champions_raises(tmp_path: Path) -> None:
    # Every role fully covered except UTILITY, which only gets one champion.
    entries = []
    counter = 0
    for role in VALID_ROLES:
        n = 1 if role == "UTILITY" else MIN_CHAMPIONS_PER_ROLE
        for _ in range(n):
            entries.append(_entry(f"Champ{counter}", [role]))
            counter += 1
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValueError, match="UTILITY"):
        load_archetypes(path)


def test_duplicate_champion_name_raises(tmp_path: Path) -> None:
    entries = []
    counter = 0
    for role in VALID_ROLES:
        for _ in range(MIN_CHAMPIONS_PER_ROLE):
            entries.append(_entry("SameName", [role]))
            counter += 1
    path = tmp_path / "roster.yaml"
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(ValueError, match="duplicate"):
        load_archetypes(path)
