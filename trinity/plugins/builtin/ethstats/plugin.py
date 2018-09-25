import os
import asyncio

from argparse import (
    ArgumentParser,
    _SubParsersAction,
)

from trinity.extensibility import (
    BaseIsolatedPlugin,
)

from trinity.plugins.builtin.ethstats.ethstats_service import (
    EthstatsService,
)

from trinity.utils.shutdown import (
    exit_with_service_and_endpoint,
)


class EthstatsPlugin(BaseIsolatedPlugin):

    @property
    def name(self) -> str:
        return 'Ethstats'

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        ethstats_parser = arg_parser.add_argument_group('ethstats (experimental)')

        ethstats_parser.add_argument(
            '--ethstats',
            action='store_true',
            help='Enable node stats reporting service',
        )

        ethstats_parser.add_argument(
            '--ethstats-server-url',
            help='Node stats server URL',
            default=os.environ.get('ETHSTATS_SERVER_URL'),
        )
        ethstats_parser.add_argument(
            '--ethstats-server-secret',
            help='Node stats server secret',
            default=os.environ.get('ETHSTATS_SERVER_SECRET'),
        )
        ethstats_parser.add_argument(
            '--ethstats-node-id',
            help='Node ID for stats server',
            default=os.environ.get('ETHSTATS_NODE_ID'),
        )
        ethstats_parser.add_argument(
            '--ethstats-node-contact',
            help='Node contact information for stats server',
            default=os.environ.get('ETHSTATS_NODE_CONTACT'),
        )

    def should_start(self) -> bool:
        if not self.context.args.ethstats:
            return False

        configuration_provided: bool = all((
            self.context.args.ethstats_server_url,
            self.context.args.ethstats_server_secret,
            self.context.args.ethstats_node_id,
            self.context.args.ethstats_node_contact,
        ))

        if not configuration_provided:
            self.logger.warning('Ethstats configuration not provided, skipping')
            return False

        return True

    def start(self) -> None:
        self.logger.info('Ethstats service started')
        self.context.event_bus.connect()

        service = EthstatsService(
            self.context,
            self.context.args.ethstats_server_url,
            self.context.args.ethstats_server_secret,
            self.context.args.ethstats_node_id,
            self.context.args.ethstats_node_contact,
        )

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        asyncio.ensure_future(exit_with_service_and_endpoint(service, self.context.event_bus))
        asyncio.ensure_future(service.run())

        loop.run_forever()
        loop.close()
