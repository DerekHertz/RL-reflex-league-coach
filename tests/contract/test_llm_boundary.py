"""Enforces the executable version of "the LLM never sees raw match JSON":
lolcoach.llm must not transitively import lolcoach.riot or lolcoach.domain.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import lolcoach.llm

_FORBIDDEN_PREFIXES = ("lolcoach.riot", "lolcoach.domain")


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _transitive_lolcoach_imports(start_module: str, seen: set[str] | None = None) -> set[str]:
    seen = seen if seen is not None else set()
    if start_module in seen:
        return seen
    seen.add(start_module)

    try:
        mod = importlib.import_module(start_module)
    except ImportError:
        return seen
    mod_file = getattr(mod, "__file__", None)
    if mod_file is None:
        return seen

    for imported in _module_imports(Path(mod_file)):
        if imported.startswith("lolcoach"):
            _transitive_lolcoach_imports(imported, seen)
    return seen


def test_llm_package_never_imports_riot_or_domain() -> None:
    llm_dir = Path(lolcoach.llm.__file__).parent
    for py_file in llm_dir.glob("*.py"):
        module_name = f"lolcoach.llm.{py_file.stem}" if py_file.stem != "__init__" else "lolcoach.llm"
        transitive = _transitive_lolcoach_imports(module_name)
        for forbidden in _FORBIDDEN_PREFIXES:
            offenders = {m for m in transitive if m == forbidden or m.startswith(forbidden + ".")}
            assert not offenders, f"{module_name} transitively imports forbidden module(s): {offenders}"
