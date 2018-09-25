import platform

import websockets

from p2p.events import (
    PeerCountRequest,
    PeerCountResponse,
)
from p2p.service import (
    BaseService,
)
from trinity.extensibility import (
    PluginContext,
)
from trinity.utils.version import (
    construct_trinity_client_identifier,
)

from trinity.plugins.builtin.ethstats.ethstats_client import (
    EthstatsClient,
    EthstatsMessage,
    timestamp_ms,
)


class EthstatsService(BaseService):
    def __init__(
        self,

        context: PluginContext,

        server_url: str,
        server_secret: str,
        node_id: str,
        node_contact: str,

        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.context = context

        self.server_url = server_url
        self.server_secret = server_secret
        self.node_id = node_id
        self.node_contact = node_contact

    async def _run(self) -> None:
        while self.is_operational:
            try:
                self.logger.info('Connecting to %s...' % self.server_url)
                async with websockets.connect(self.server_url) as websocket:
                    client: EthstatsClient = EthstatsClient(
                        websocket,
                        self.node_id,
                        token=self.cancel_token,
                    )

                    self.run_child_service(client)

                    await self.wait_first(
                        self.server_handler(client),
                        self.statistics_handler(client),
                    )
            except websockets.ConnectionClosed as e:
                self.logger.info('Connection to %s is closed: %s' % (self.server_url, e))

            self.logger.info('Reconnecting in 5s...')
            await self.sleep(5)

    # Wait for messages from server, respond when they arrive
    async def server_handler(self, client: EthstatsClient) -> None:
        while self.is_operational:
            message: EthstatsMessage = await client.recv()

            if message.command == 'node-pong':
                await client.send_latency((timestamp_ms() - message.data['clientTime']) // 2)
            elif message.command == 'history':
                # TODO: send actual history
                pass
            else:
                self.logger.info('Server message received')

    # Periodically send statistics and ping server to calculate latency
    async def statistics_handler(self, client: EthstatsClient) -> None:
        await client.send_hello(self.server_secret, self.get_node_info())

        while self.is_operational:
            await client.send_node_ping()
            await client.send_stats(await self.get_node_stats())

            await self.sleep(5)

    def get_node_info(self) -> dict:
        return {
            'name': self.node_id,
            'contact': self.node_contact,
            'os': platform.system(),
            'os_v': platform.release(),
            'client': construct_trinity_client_identifier(),
            'canUpdateHistory': False,
        }

    async def get_node_stats(self) -> dict:
        response: PeerCountResponse = await self.context.event_bus.request(
            PeerCountRequest()
        )

        return {
            'active': True,
            'peers': response.peer_count,
        }
