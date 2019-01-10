from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
from typing import (
    Set,
)

from trinity.extensibility import (
    BaseMainProcessPlugin,
)


class SyncModeParserPlugin(BaseMainProcessPlugin):

    def __init__(self, sync_modes: Set[str], default_sync_mode: str) -> None:
        # Other plugins can get a reference to this plugin instance
        # and add another mode (e.g. warp)
        self.sync_modes = sync_modes
        self.default_mode = default_sync_mode

    @property
    def name(self) -> str:
        return "Sync Mode Parser"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        syncing_parser = arg_parser.add_argument_group('sync mode')
        mode_parser = syncing_parser.add_mutually_exclusive_group()
        mode_parser.add_argument(
            '--sync-mode',
            choices=self.sync_modes,
            default=self.default_mode,
        )
