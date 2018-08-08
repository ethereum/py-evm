from abc import (
    abstractmethod
)
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import sys

from trinity.config import (
    ChainConfig,
)
from trinity.extensibility import (
    BasePlugin,
)

from trinity.plugins.builtin.attach.console import (
    console,
)


class AttachPlugin(BasePlugin):

    @property
    def name(self) -> str:
        return "Attach"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'attach',
            help='open an REPL attached to a currently running chain',
        )

        attach_parser.set_defaults(func=self.run_console)

    @abstractmethod
    def console(self, chain_config: ChainConfig) -> None:
        raise NotImplementedError('Must be implemented in subclasses')

    def run_console(self, args: Namespace, chain_config: ChainConfig) -> None:
        try:
            self.console(chain_config)
        except FileNotFoundError as err:
            self.logger.error(str(err))
            sys.exit(1)


class IPythonShellAttachPlugin(AttachPlugin):

    def console(self, chain_config: ChainConfig) -> None:
        console(chain_config.jsonrpc_ipc_path, use_ipython=True)


class VanillaShellAttachPlugin(AttachPlugin):

    def console(self, chain_config: ChainConfig) -> None:
        console(chain_config.jsonrpc_ipc_path, use_ipython=False)
