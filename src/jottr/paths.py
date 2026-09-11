"""Resolve bundled and system-installed Jottr data directories."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def data_roots() -> list[Path]:
    """Candidate roots that may contain icons/, translations/, help/."""
    roots: list[Path] = []
    pkg = package_dir()
    roots.append(pkg)

    # Editable / src-layout checkout: <repo>/src/jottr -> <repo>
    repo_root = pkg.parents[1]
    if (repo_root / "pyproject.toml").is_file() or (repo_root / "setup.py").is_file():
        roots.append(repo_root)

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))

    for share in (
        Path("/app/share/jottr"),
        Path("/usr/share/jottr"),
        Path("/usr/local/share/jottr"),
    ):
        if share.is_dir():
            roots.append(share)

    env_data = os.environ.get("JOTTR_DATA_DIR")
    if env_data:
        env_path = Path(env_data)
        if env_path.is_dir():
            roots.append(env_path)

    # Preserve unique order
    seen: set[Path] = set()
    ordered: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def find_data_dir(*parts: str) -> Path | None:
    """Return the first existing directory joined onto a data root."""
    for root in data_roots():
        candidate = root.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    return None


def find_data_file(*parts: str) -> Path | None:
    """Return the first existing file joined onto a data root."""
    for root in data_roots():
        candidate = root.joinpath(*parts)
        if candidate.is_file():
            return candidate
    return None
