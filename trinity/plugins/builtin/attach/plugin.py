from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import sys

from trinity.config import (
    TrinityConfig,
)
from trinity.extensibility import (
    BaseMainProcessPlugin,
)

from trinity.plugins.builtin.attach.console import (
    console,
)


class AttachPlugin(BaseMainProcessPlugin):

    def __init__(self, use_ipython: bool = True) -> None:
        super().__init__()
        self.use_ipython = use_ipython

    @property
    def name(self) -> str:
        return "Attach"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'attach',
            help='open an REPL attached to a currently running chain',
        )

        attach_parser.set_defaults(func=self.run_console)

    def run_console(self, args: Namespace, trinity_config: TrinityConfig) -> None:
        try:
            console(trinity_config.jsonrpc_ipc_path, use_ipython=self.use_ipython)
        except FileNotFoundError as err:
            self.logger.error(str(err))
            sys.exit(1)
