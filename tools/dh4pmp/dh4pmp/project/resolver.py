"""
Config resolver for dh4pmp CLI.

Resolution order: CLI args → config file → hardcoded defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


# ---------------------------------------------------------------------------
# Hardcoded defaults – sidste faldback
# ---------------------------------------------------------------------------

DEFAULTS = {
    "author": "Henrik Kragh Sørensen",
    "parent_dir": str(Path.home() / "Documents" / "dh4pmp"),
    "git_init": True,
    "github": False,
    "conda": True,
    "python_version": "3.11",
}

CONFIG_SEARCH_PATHS = [
    Path.home() / ".config" / "dh4pmp" / "config.yaml",
]


# ---------------------------------------------------------------------------
# Dataclass der holder de endelige værdier
# ---------------------------------------------------------------------------

@dataclass
class ProjectConfig:
    """Resolved configuration for a project creation run."""

    project_name: str    # med dash: mappenavn + GitHub repo-navn
    package_name: str    # med underscore: Python-pakke + conda env
    template: str
    author: str
    parent_dir: Path
    description: str
    git_init: bool
    github: bool
    github_visibility: str
    conda: bool
    python_version: str

    @property
    def project_dir(self) -> Path:
        return self.parent_dir / self.project_name

    @property
    def conda_env(self) -> str:
        return self.package_name


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def load_user_config() -> dict:
    """
    Load user config from first existing path in CONFIG_SEARCH_PATHS.

    Returns empty dict if no config file found.
    """
    for path in CONFIG_SEARCH_PATHS:
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return data.get("defaults", data)  # støtter både flad og nestet yaml
    return {}


def resolve(
    *,
    project_name: str,
    template: str,
    description: str,
    author: Optional[str] = None,
    parent_dir: Optional[str] = None,
    git_init: Optional[bool] = None,
    github: Optional[bool] = None,
    github_visibility: str = "private",
    conda: Optional[bool] = None,
    python_version: Optional[str] = None,
) -> ProjectConfig:
    """
    Resolve final config by merging CLI args, user config, and hardcoded defaults.

    Args:
        project_name: Påkrævet – projektnavn.
        template: Påkrævet – 'full' eller 'minimal'.
        description: Projektbeskrivelse (kan være tom streng).
        author: Overskriver config/default hvis angivet.
        parent_dir: Overskriver config/default hvis angivet.
        git_init: Overskriver config/default hvis angivet.
        github: Overskriver config/default hvis angivet.
        github_visibility: 'public' eller 'private'.
        python_version: Overskriver config/default hvis angivet.

    Returns:
        ProjectConfig med alle felter udfyldt.
    """
    user = load_user_config()

    def resolve_value(key: str, cli_value):
        """Prioritet: CLI → user config → hardcoded default."""
        if cli_value is not None:
            return cli_value
        if key in user:
            return user[key]
        if key in DEFAULTS:
            return DEFAULTS[key]
        raise ValueError(f"Manglende påkrævet parameter: '{key}' – angiv via CLI eller config.yaml")

    # Normaliser: dash/mellemrum → underscore til Python-brug
    package_name = project_name.replace("-", "_").replace(" ", "_")

    return ProjectConfig(
        project_name=project_name,
        package_name=package_name,
        template=template,
        description=description,
        author=resolve_value("author", author),
        parent_dir=Path(resolve_value("parent_dir", parent_dir)).expanduser(),
        git_init=resolve_value("git_init", git_init),
        github=resolve_value("github", github),
        github_visibility=github_visibility,
        conda=resolve_value("conda", conda),
        python_version=resolve_value("python_version", python_version),
    )
