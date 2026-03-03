"""
Project generator for dh4pmp CLI.

Idempotent: kør flere gange – eksisterende filer røres ikke,
manglende mapper og filer tilføjes ("opad").
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .resolver import ProjectConfig
from .discover import discover_packages, extra_paths, package_names


# ---------------------------------------------------------------------------
# Stier til templates
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
COMMON_DIR = TEMPLATES_DIR / "common"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class ProjectGenerator:
    """
    Opretter eller opdaterer et projekt idempotent.

    Mapper: oprettes hvis de ikke findes (mkdir -p).
    Filer:  oprettes kun hvis de IKKE allerede eksisterer.
    """

    def __init__(self, config: ProjectConfig, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.project_dir = config.project_dir
        self.template_dir = TEMPLATES_DIR / config.template

        self._jinja = Environment(
            loader=FileSystemLoader([str(self.template_dir), str(COMMON_DIR)]),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

        # Opdager dh4pmp_tools-pakker dynamisk ved oprettelsestidspunktet
        self._packages = discover_packages()
        pkg_names = package_names(self._packages)
        pkg_paths = extra_paths(self._packages)

        if self._packages and not dry_run:
            print(f"  Opdagede {len(self._packages)} dh4pmp_tools-pakker: {', '.join(pkg_names)}")

        self._template_vars = {
            "project_name": config.project_name,
            "package_name": config.package_name,
            "conda_env": config.conda_env,
            "description": config.description,
            "author": config.author,
            "date": date.today().isoformat(),
            "template": config.template,
            "command": f"dh4pmp create {config.template if config.template == 'minimal' else 'project'}",
            "python_version": config.python_version,
            "dh4pmp_package_names": pkg_names,
            "dh4pmp_extra_paths": pkg_paths,
        }

        self._created_folders: list[Path] = []
        self._created_files: list[Path] = []
        self._skipped_files: list[Path] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Kør fuld projektgenerering."""
        self._create_folders()
        self._create_files()

        if self.config.git_init and not self.dry_run:
            self._git_init()

        if self.config.github and not self.dry_run:
            self._github_create()

        if self.config.conda and not self.dry_run:
            self._conda_create()

        self._print_summary()

    # ------------------------------------------------------------------
    # Mapper
    # ------------------------------------------------------------------

    def _create_folders(self) -> None:
        folders_file = self.template_dir / "folders.yaml"
        if not folders_file.exists():
            raise FileNotFoundError(f"Mangler {folders_file}")

        with open(folders_file) as f:
            data = yaml.safe_load(f)

        for folder_template in data.get("folders", []):
            # Render Jinja2 i mappestien (fx src/{{ project_name }})
            rendered = self._jinja.from_string(folder_template).render(self._template_vars)
            folder_path = self.project_dir / rendered

            if self.dry_run:
                marker = " [eksisterer]" if folder_path.exists() else " [ny]"
                print(f"  [dry-run] mappe: {folder_path}{marker}")
            else:
                folder_path.mkdir(parents=True, exist_ok=True)
                # .gitkeep så tomme mapper trackes
                gitkeep = folder_path / ".gitkeep"
                if not gitkeep.exists():
                    gitkeep.touch()
                self._created_folders.append(folder_path)

    # ------------------------------------------------------------------
    # Filer
    # ------------------------------------------------------------------

    def _create_files(self) -> None:
        files_file = self.template_dir / "files.yaml"
        if not files_file.exists():
            raise FileNotFoundError(f"Mangler {files_file}")

        with open(files_file) as f:
            data = yaml.safe_load(f)

        for entry in data.get("files", []):
            src_name: str = entry["src"]
            dst_template: str = entry["dst"]

            # Render destination-sti (fx src/{{ project_name }}/__init__.py)
            dst_rel = self._jinja.from_string(dst_template).render(self._template_vars)
            dst_path = self.project_dir / dst_rel

            if self.dry_run:
                marker = " [eksisterer – springes over]" if dst_path.exists() else " [ny]"
                print(f"  [dry-run] fil:   {dst_path}{marker}")
                continue

            # Idempotens: spring over hvis filen allerede findes
            if dst_path.exists():
                self._skipped_files.append(dst_path)
                continue

            # Render indhold
            content = self._render_template(src_name)

            # Skriv
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_text(content, encoding="utf-8")
            self._created_files.append(dst_path)

    def _render_template(self, src_name: str) -> str:
        """Render en template-fil med Jinja2. Ikke-.j2-filer kopieres råt."""
        if src_name.endswith(".j2"):
            tmpl = self._jinja.get_template(src_name)
            return tmpl.render(self._template_vars)
        else:
            # Rå fil – ingen Jinja2-processing
            raw_path = self._find_raw(src_name)
            return raw_path.read_text(encoding="utf-8")

    def _find_raw(self, filename: str) -> Path:
        """Find rå fil i template_dir eller common."""
        for base in (self.template_dir, COMMON_DIR):
            p = base / filename
            if p.exists():
                return p
        raise FileNotFoundError(f"Template-fil ikke fundet: {filename}")

    # ------------------------------------------------------------------
    # Git + GitHub
    # ------------------------------------------------------------------

    def _git_init(self) -> None:
        """Initialiser git-repo hvis det ikke allerede eksisterer."""
        git_dir = self.project_dir / ".git"
        if git_dir.exists():
            print("  git: allerede initialiseret – springer over")
            return

        try:
            subprocess.run(["git", "init"], cwd=self.project_dir, check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=self.project_dir, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Initial commit: {self.config.project_name}"],
                cwd=self.project_dir, check=True, capture_output=True
            )
            print("  ✓ git init + initial commit")
        except FileNotFoundError:
            print("  ✗ git ikke fundet – springer over")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ git fejlede: {e}")

    def _conda_create(self) -> None:
        """Opret conda-miljø fra environment.yaml hvis det ikke allerede eksisterer."""
        env_name = self.config.conda_env
        try:
            # Tjek om env allerede eksisterer
            result = subprocess.run(
                ["conda", "env", "list"],
                capture_output=True, text=True, check=True
            )
            existing = [line.split()[0] for line in result.stdout.splitlines()
                        if line and not line.startswith("#")]
            if env_name in existing:
                print(f"  conda: miljø '{env_name}' eksisterer allerede – springer over")
                return

            env_yaml = self.project_dir / "environment.yaml"
            if env_yaml.exists():
                subprocess.run(
                    ["conda", "env", "create", "-f", str(env_yaml)],
                    check=True
                )
            else:
                subprocess.run(
                    ["conda", "create", "-n", env_name,
                     f"python={self.config.python_version}", "-y"],
                    check=True
                )
            print(f"  ✓ conda env oprettet: {env_name}")
        except FileNotFoundError:
            print("  ✗ conda ikke fundet i PATH – springer over")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ conda fejlede: {e}")

    def _github_create(self) -> None:
        """Opret GitHub-repo via gh CLI."""
        try:
            # Tjek at gh er autentificeret
            auth_check = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True
            )
            if auth_check.returncode != 0:
                print("  ✗ gh CLI ikke autentificeret. Kør: gh auth login")
                return

            subprocess.run(
                [
                    "gh", "repo", "create", self.config.project_name,
                    f"--{self.config.github_visibility}",
                    "--source", str(self.project_dir),
                    "--push",
                ],
                check=True,
            )
            print(f"  ✓ GitHub repo: https://github.com/hksorensen/{self.config.project_name}")
        except FileNotFoundError:
            print("  ✗ gh CLI ikke installeret. Se: https://cli.github.com")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ gh fejlede: {e}")

    # ------------------------------------------------------------------
    # Opsummering
    # ------------------------------------------------------------------

    def _print_summary(self) -> None:
        print(f"\n✓ {self.config.project_name} klar i {self.project_dir}")

        if self._created_files:
            print(f"  Nye filer ({len(self._created_files)}):")
            for f in self._created_files:
                print(f"    + {f.relative_to(self.project_dir)}")

        if self._skipped_files:
            print(f"  Eksisterende filer bibeholdt ({len(self._skipped_files)}):")
            for f in self._skipped_files:
                print(f"    = {f.relative_to(self.project_dir)}")

        print(f"\n  cd {self.project_dir}")
        if self.config.template == "full":
            if not self.config.conda:
                print(f"  conda create -n {self.config.conda_env} python={self.config.python_version}")
            print(f"  conda activate {self.config.conda_env}")
