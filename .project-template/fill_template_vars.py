#!/usr/bin/env python3

import os
import re
import sys
from pathlib import Path


def _find_files(project_root: Path) -> list[str]:
    PATH_EXCLUDE_PATTERN = r"\.git($|\/)|venv|_build"
    FILE_EXCLUDE_PATTERN = r"fill_template_vars\.py|\.swp$"

    filepaths = []
    for dir_path, _, file_names in os.walk(project_root):
        if not re.search(PATH_EXCLUDE_PATTERN, dir_path):
            for file in file_names:
                if not re.search(FILE_EXCLUDE_PATTERN, file):
                    filepaths.append(str(Path(dir_path, file)))

    return filepaths


def _replace(pattern: str, replacement: str, project_root: Path):
    print(f"Replacing values: {pattern}")
    for file in _find_files(project_root):
        try:
            with open(file) as f:
                content = f.read()
            content = re.sub(pattern, replacement, content)
            with open(file, "w") as f:
                f.write(content)
        except UnicodeDecodeError:
            pass


def main():
    project_root = Path(os.path.realpath(sys.argv[0])).parent.parent

    module_name = input("What is your python module name? ")

    pypi_input = input(f"What is your pypi package name? (default: {module_name}) ")
    pypi_name = pypi_input or module_name

    repo_input = input(f"What is your github project name? (default: {pypi_name}) ")
    repo_name = repo_input or pypi_name

    rtd_input = input(
        f"What is your readthedocs.org project name? (default: {pypi_name}) "
    )
    rtd_name = rtd_input or pypi_name

    project_input = input(
        f"What is your project name (ex: at the top of the README)? (default: {repo_name}) "
    )
    project_name = project_input or repo_name

    short_description = input("What is a one-liner describing the project? ")

    _replace("<MODULE_NAME>", module_name, project_root)
    _replace("<PYPI_NAME>", pypi_name, project_root)
    _replace("<REPO_NAME>", repo_name, project_root)
    _replace("<RTD_NAME>", rtd_name, project_root)
    _replace("<PROJECT_NAME>", project_name, project_root)
    _replace("<SHORT_DESCRIPTION>", short_description, project_root)

    os.makedirs(project_root / module_name, exist_ok=True)
    Path(project_root / module_name / "__init__.py").touch()
    Path(project_root / module_name / "py.typed").touch()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        pass
