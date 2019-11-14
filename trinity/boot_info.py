from argparse import Namespace
from typing import Dict, NamedTuple

from trinity.config import TrinityConfig


class BootInfo(NamedTuple):
    args: Namespace
    trinity_config: TrinityConfig
    profile: bool
    child_process_log_level: int
    logger_levels: Dict[str, int]
