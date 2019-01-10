from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import sys

from trinity.config import (
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.extensibility import (
    BaseMainProcessPlugin,
)

from trinity.plugins.builtin.attach.console import (
    console,
    db_shell,
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


class DbShellPlugin(BaseMainProcessPlugin):

    def __init__(self, use_ipython: bool = True) -> None:
        super().__init__()
        self.use_ipython = use_ipython

    @property
    def name(self) -> str:
        return "DB Shell"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'db-shell',
            help='open a REPL to inspect the db',
        )

        attach_parser.set_defaults(func=self.run_shell)

    def run_shell(self, args: Namespace, trinity_config: TrinityConfig) -> None:

        if trinity_config.has_app_config(Eth1AppConfig):
            config = trinity_config.get_app_config(Eth1AppConfig)
            db_shell(self.use_ipython, config.database_dir)
        else:
            self.logger.error("DB Shell does only support the Ethereum 1 node at this time")
