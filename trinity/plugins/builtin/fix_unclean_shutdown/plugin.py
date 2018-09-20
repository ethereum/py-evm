from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import time

from trinity.config import (
    ChainConfig,
)
from trinity.extensibility import (
    BaseMainProcessPlugin,
)
from trinity.utils.ipc import (
    kill_process_id_gracefully,
)


class FixUncleanShutdownPlugin(BaseMainProcessPlugin):

    @property
    def name(self) -> str:
        return "Fix Unclean Shutdown"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:

        attach_parser = subparser.add_parser(
            'fix-unclean-shutdown',
            help='close any dangling processes from a previous unclean shutdown',
        )

        attach_parser.set_defaults(func=self.fix_unclean_shutdown)

    def fix_unclean_shutdown(self, args: Namespace, chain_config: ChainConfig) -> None:
        self.logger.info("Cleaning up unclean shutdown...")

        self.logger.info("Searching for process id files in %s..." % chain_config.data_dir)
        pidfiles = tuple(chain_config.data_dir.glob('*.pid'))
        if len(pidfiles) > 1:
            self.logger.info('Found %d processes from a previous run. Closing...' % len(pidfiles))
        elif len(pidfiles) == 1:
            self.logger.info('Found 1 process from a previous run. Closing...')
        else:
            self.logger.info('Found 0 processes from a previous run. No processes to kill.')

        for pidfile in pidfiles:
            process_id = int(pidfile.read_text())
            kill_process_id_gracefully(process_id, time.sleep, self.logger)
            try:
                pidfile.unlink()
                self.logger.info(
                    'Manually removed %s after killing process id %d' % (pidfile, process_id)
                )
            except FileNotFoundError:
                self.logger.debug(
                    'pidfile %s was gone after killing process id %d' % (pidfile, process_id)
                )

        db_ipc = chain_config.database_ipc_path
        try:
            db_ipc.unlink()
            self.logger.info(
                'Removed a dangling IPC socket file for database connections at %s', db_ipc
            )
        except FileNotFoundError:
            self.logger.debug(
                'The IPC socket file for database connections at %s was already gone', db_ipc
            )

        jsonrpc_ipc = chain_config.jsonrpc_ipc_path
        try:
            jsonrpc_ipc.unlink()
            self.logger.info(
                'Removed a dangling IPC socket file for JSON-RPC connections at %s',
                jsonrpc_ipc,
            )
        except FileNotFoundError:
            self.logger.debug(
                'The IPC socket file for JSON-RPC connections at %s was already gone',
                jsonrpc_ipc,
            )
