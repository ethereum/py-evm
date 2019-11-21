import argparse
import enum
from typing import Any


@enum.unique
class TrackingBackend(enum.Enum):
    SQLITE3 = 'sqlite3'
    MEMORY = 'memory'
    DO_NOT_TRACK = 'do-not-track'


class NormalizeTrackingBackend(argparse.Action):
    """
    Normalized the --network-tracking-backend CLI arg into the proper Enum type.
    """
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str = None) -> None:
        try:
            tracking_backend = TrackingBackend(value)
        except TypeError:
            raise argparse.ArgumentError(
                self,
                (
                    "Unknown option for --network-tracking-backend.  Must be one of "
                    "`sqlite3/memory/disabled`.  Got '{value}'"
                ),
            )

        setattr(namespace, self.dest, tracking_backend)
