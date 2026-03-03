"""
dh4pmp – Digital Humanities project management CLI.
"""

import click

from .commands.create import create


@click.group()
@click.version_option()
def cli() -> None:
    """dh4pmp – værktøjer til DH4PMP-forskningsprojekter."""
    pass


cli.add_command(create)


if __name__ == "__main__":
    cli()
