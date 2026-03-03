"""
dh4pmp create – subkommandoer til projektoprettelse.
"""

from __future__ import annotations

from typing import Optional

import click

from ...project.resolver import resolve
from ...project.generator import ProjectGenerator


# ---------------------------------------------------------------------------
# Fælles options som decorator-fabrik
# ---------------------------------------------------------------------------

def common_options(f):
    """Delte CLI-options til alle create-subkommandoer."""
    decorators = [
        click.option("--author", default=None, help="Forfatter (default: fra config/hardcoded)"),
        click.option("--parent", default=None, metavar="DIR",
                     help="Forældremapp (default: ~/Documents/dh4pmp)"),
        click.option("--description", "-d", default="", help="Kort projektbeskrivelse"),
        click.option("--git/--no-git", default=None,
                     help="Initialiser git-repo (default: ja)"),
        click.option("--github/--no-github", default=None,
                     help="Opret GitHub-repo via gh CLI (default: nej)"),
        click.option("--visibility", default="private",
                     type=click.Choice(["public", "private"]),
                     help="GitHub repo-synlighed (default: private)"),
        click.option("--conda/--no-conda", default=None,
                     help="Opret conda-miljø (default: ja for full, nej for minimal)"),
        click.option("--dry-run", is_flag=True,
                     help="Vis hvad der ville ske – opret intet"),
    ]
    for d in reversed(decorators):
        f = d(f)
    return f


# ---------------------------------------------------------------------------
# create-gruppe
# ---------------------------------------------------------------------------

@click.group()
def create():
    """Opret nyt projekt eller pakke."""
    pass


# ---------------------------------------------------------------------------
# dh4pmp create project
# ---------------------------------------------------------------------------

@create.command()
@click.argument("name")
@common_options
def project(
    name: str,
    author: Optional[str],
    parent: Optional[str],
    description: str,
    git: Optional[bool],
    github: Optional[bool],
    visibility: str,
    conda: Optional[bool],
    dry_run: bool,
) -> None:
    """
    Opret fuldt forskningsprojekt med kodestruktur.

    NAME: projektnavn (bruges som mappenavn og pakkenavn)

    \b
    Eksempler:
      dh4pmp create project mit-projekt
      dh4pmp create project mit-projekt --github --visibility public
      dh4pmp create project mit-projekt --parent ~/Documents --dry-run
    """
    config = resolve(
        project_name=name,
        template="full",
        description=description,
        author=author,
        parent_dir=parent,
        git_init=git,
        github=github,
        github_visibility=visibility,
        conda=conda,
    )

    _echo_plan(config, dry_run)

    gen = ProjectGenerator(config, dry_run=dry_run)
    gen.run()


# ---------------------------------------------------------------------------
# dh4pmp create minimal
# ---------------------------------------------------------------------------

@create.command()
@click.argument("name")
@common_options
def minimal(
    name: str,
    author: Optional[str],
    parent: Optional[str],
    description: str,
    git: Optional[bool],
    github: Optional[bool],
    visibility: str,
    conda: Optional[bool],
    dry_run: bool,
) -> None:
    """
    Opret minimalt projekt – artikel, eksperiment eller kladde uden pakkestruktur.

    NAME: projektnavn (bruges som mappenavn)

    \b
    Eksempler:
      dh4pmp create minimal min-artikel
      dh4pmp create minimal konference-abstract --no-git
    """
    config = resolve(
        project_name=name,
        template="minimal",
        description=description,
        author=author,
        parent_dir=parent,
        git_init=git,
        github=github,
        github_visibility=visibility,
        conda=conda,
    )

    _echo_plan(config, dry_run)

    gen = ProjectGenerator(config, dry_run=dry_run)
    gen.run()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _echo_plan(config, dry_run: bool) -> None:
    """Print hvad der er ved at ske."""
    mode = " [DRY RUN]" if dry_run else ""
    click.echo(f"\nOpretter '{config.project_name}' ({config.template}){mode}")
    click.echo(f"  Placering: {config.project_dir}")
    click.echo(f"  Forfatter: {config.author}")
    if config.description:
        click.echo(f"  Beskrivelse: {config.description}")
    click.echo(f"  Git: {'ja' if config.git_init else 'nej'}")
    if config.github:
        click.echo(f"  GitHub: {config.github_visibility}")
    click.echo()
