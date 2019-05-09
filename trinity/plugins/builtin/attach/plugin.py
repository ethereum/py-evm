from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import pkg_resources
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


def is_ipython_available() -> bool:
    try:
        pkg_resources.get_distribution('IPython')
    except pkg_resources.DistributionNotFound:
        return False
    else:
        return True


class AttachPlugin(BaseMainProcessPlugin):
    @property
    def name(self) -> str:
        return "Attach"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'attach',
            help='open an REPL attached to a currently running chain',
        )

        attach_parser.set_defaults(func=cls.run_console)

    @classmethod
    def run_console(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        try:
            console(trinity_config.jsonrpc_ipc_path, use_ipython=is_ipython_available())
        except FileNotFoundError as err:
            cls.get_logger().error(str(err))
            sys.exit(1)


class DbShellPlugin(BaseMainProcessPlugin):
    @property
    def name(self) -> str:
        return "DB Shell"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'db-shell',
            help='open a REPL to inspect the db',
        )

        attach_parser.set_defaults(func=cls.run_shell)

    @classmethod
    def run_shell(cls, args: Namespace, trinity_config: TrinityConfig) -> None:

        if trinity_config.has_app_config(Eth1AppConfig):
            config = trinity_config.get_app_config(Eth1AppConfig)
            db_shell(is_ipython_available(), config.database_dir, trinity_config)
        else:
            cls.get_logger().error(
                "DB Shell only supports the Ethereum 1 node at this time"
            )
