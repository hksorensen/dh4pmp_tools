"""
Setup script with post-install hook for citation-tools.
"""

from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
import subprocess
import sys


class PostDevelopCommand(develop):
    """Post-installation for development mode."""
    def run(self):
        develop.run(self)
        print("\n" + "="*60)
        print("Running first-time configuration...")
        print("="*60 + "\n")
        try:
            subprocess.check_call([sys.executable, '-m', 'citation_tools.setup_config'])
        except Exception as e:
            print(f"\nNote: Auto-configuration failed: {e}")
            print("You can run setup manually with: cite-setup\n")


class PostInstallCommand(install):
    """Post-installation for install mode."""
    def run(self):
        install.run(self)
        print("\n" + "="*60)
        print("Running first-time configuration...")
        print("="*60 + "\n")
        try:
            subprocess.check_call([sys.executable, '-m', 'citation_tools.setup_config'])
        except Exception as e:
            print(f"\nNote: Auto-configuration failed: {e}")
            print("You can run setup manually with: cite-setup\n")


# Use pyproject.toml for most configuration, but add cmdclass here
setup(
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand,
    },
)
