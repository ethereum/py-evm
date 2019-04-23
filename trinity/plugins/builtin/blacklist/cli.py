import argparse
from typing import Any

from trinity.constants import TrackingBackend


class NormalizeTrackingBackend(argparse.Action):
    """
    Normalized the --enode-tracking-backend CLI arg into the proper Enum type.
    """
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str=None) -> None:
        try:
            tracking_backend = TrackingBackend(value)
        except TypeError as err:
            raise argparse.ArgumentError(
                self,
                (
                    "Unknown option for --enode-tracking-backend.  Must be one of "
                    "`sqlite3/memory/disabled`.  Got '{value}'"
                ),
            )

        setattr(namespace, self.dest, tracking_backend)
