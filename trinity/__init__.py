import re
import subprocess
import sys
from pathlib import Path

import pkg_resources


def find_version(setup_trinity_path: Path) -> str:
    version = ''
    try:
        text = setup_trinity_path.read_text()
        version_match = re.search(r"version=['\"]([^'\"]*)['\"]", text)
        if version_match:
            version = version_match.group(1)
    except IOError:
        pass
    return version


# TODO: update this to use the `trinity` version once extracted from py-evm
__version__: str
SETUP_FILE_PATH = Path(__file__).parent.parent
try:
    __version__ = pkg_resources.get_distribution("trinity").version
except pkg_resources.DistributionNotFound:
    __version__ = find_version(SETUP_FILE_PATH / "setup_trinity.py")

try:
    git_commit_id = subprocess.check_output(['git', '-C', SETUP_FILE_PATH, 'rev-parse', 'HEAD'],
                                            stderr=subprocess.DEVNULL, encoding='UTF-8')
    __version__ += "-dev-{}".format(git_commit_id[:8])
except subprocess.CalledProcessError:
    pass

# This is to ensure we call setup_trace_logging() before anything else.
import eth as _eth_module  # noqa: F401

if sys.platform in {'darwin', 'linux'}:
    # Set `uvloop` as the default event loop
    import asyncio  # noqa: E402
    import uvloop  # noqa: E402
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from .main import (  # noqa: F401
    main,
)
