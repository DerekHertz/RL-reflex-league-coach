"""On-disk cache for raw Riot match/timeline JSON.

Match and timeline data is immutable once a game ends -- so this cache is
written once, never invalidated, and has no TTL. It lives on the filesystem
(gzipped), not in the database: the payloads are large (a timeline can be
1-3 MB), never queried relationally, and need to survive every schema change
made while iterating on detectors. This is what makes `lolcoach replay` free.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Literal, Protocol

Kind = Literal["match", "timeline"]


class RawCache(Protocol):
    def get(self, kind: Kind, match_id: str) -> dict | None: ...
    def put(self, kind: Kind, match_id: str, payload: dict) -> None: ...
    def has(self, kind: Kind, match_id: str) -> bool: ...


class FileRawCache:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, kind: Kind, match_id: str) -> Path:
        platform = match_id.split("_", 1)[0].upper()
        return self._root / kind / platform / f"{match_id}.json.gz"

    def has(self, kind: Kind, match_id: str) -> bool:
        return self._path(kind, match_id).exists()

    def get(self, kind: Kind, match_id: str) -> dict | None:
        path = self._path(kind, match_id)
        if not path.exists():
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)

    def put(self, kind: Kind, match_id: str, payload: dict) -> None:
        path = self._path(kind, match_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.rename(path)
