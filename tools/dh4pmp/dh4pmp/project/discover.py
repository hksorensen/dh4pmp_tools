"""
Dynamisk opdagelse af dh4pmp_tools-pakker til brug i
pyrightconfig.json, .cursor/rules og .claude/settings.local.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


DH4PMP_TOOLS_ROOT = Path.home() / "Documents" / "dh4pmp_tools"


class DiscoveredPackage(NamedTuple):
    name: str        # fx "caching"
    path: Path       # absolut sti til pakke-roden


def discover_packages(tools_root: Path = DH4PMP_TOOLS_ROOT) -> list[DiscoveredPackage]:
    """
    Find alle pakker under packages/ i dh4pmp_tools.

    Kriterium: undermappe med pyproject.toml eller __init__.py et niveau ned.
    Ignorerer mapper der starter med '.' eller '_', backup-mapper og README.

    Args:
        tools_root: Rod af dh4pmp_tools-repo'et.

    Returns:
        Sorteret liste af DiscoveredPackage.
    """
    packages_dir = tools_root / "packages"
    if not packages_dir.exists():
        return []

    result = []
    for item in sorted(packages_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith((".", "_")):
            continue
        if item.name in ("README.md", "VERSIONING_SUMMARY.md"):
            continue
        if "backup" in item.name.lower():
            continue

        # Tjek at det ligner en Python-pakke
        has_pyproject = (item / "pyproject.toml").exists()
        # Kig et niveau ned efter __init__.py
        has_init = any((item / sub / "__init__.py").exists() for sub in [item.name, item.name.replace("-", "_")])

        if has_pyproject or has_init:
            result.append(DiscoveredPackage(name=item.name, path=item))

    return result


def extra_paths(packages: list[DiscoveredPackage]) -> list[str]:
    """
    Returner liste af absolutte stier til brug i pyrightconfig.json extraPaths.
    Inkluderer både pakke-roden og eventuel src/-undermappe.
    """
    paths = []
    for pkg in packages:
        paths.append(str(pkg.path))
        src = pkg.path / "src"
        if src.exists():
            paths.append(str(src))
    return paths


def package_names(packages: list[DiscoveredPackage]) -> list[str]:
    """Returner pakkenavne normaliseret til Python-import-stil."""
    return [p.name.replace("-", "_") for p in packages]
