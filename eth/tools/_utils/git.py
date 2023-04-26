import subprocess

from eth_utils import (
    to_text,
)


def get_version_from_git() -> str:
    version = subprocess.check_output(["git", "describe"]).strip()
    return to_text(version)
