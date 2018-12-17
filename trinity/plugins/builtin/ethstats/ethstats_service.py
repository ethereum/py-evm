import platform

import websockets

from eth.chains.base import (
    BaseChain,
)
from p2p.events import (
    PeerCountRequest,
)
from p2p.service import (
    BaseService,
)
from trinity import (
    __version__,
)
from trinity.extensibility import (
    PluginContext,
)
from trinity.constants import (
    SYNC_LIGHT,
    TO_NETWORKING_BROADCAST_CONFIG,
)
from trinity.db.manager import (
    create_db_manager,
)
from trinity.plugins.builtin.light_peer_chain_bridge.light_peer_chain_bridge import (
    EventBusLightPeerChain,
)
from trinity.utils.version import (
    construct_trinity_client_identifier,
)

from trinity.plugins.builtin.ethstats.ethstats_client import (
    EthstatsClient,
    EthstatsMessage,
    EthstatsData,
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
    ) -> None:
        super().__init__()

        self.context = context

        self.server_url = server_url
        self.server_secret = server_secret
        self.node_id = node_id
        self.node_contact = node_contact

        self.chain = self.get_chain()

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
            await client.send_block(self.get_node_block())

            await self.sleep(5)

    def get_node_info(self) -> EthstatsData:
        '''Getter for data that should be sent once, on start-up.'''
        return {
            'name': self.node_id,
            'contact': self.node_contact,
            'node': construct_trinity_client_identifier(),
            'net': self.context.trinity_config.network_id,
            'port': self.context.trinity_config.port,
            'os': platform.system(),
            'os_v': platform.release(),
            'client': __version__,
            'canUpdateHistory': False,
        }

    def get_node_block(self) -> EthstatsData:
        '''Getter for data that should be sent on every new chain tip change.'''
        head = self.chain.get_canonical_head()

        return {
            'number': head.block_number,
            'hash': head.hex_hash,
            'difficulty': head.difficulty,
            'totalDifficulty': self.chain.get_score(head.hash),
            'transactions': [],
            'uncles': [],
        }

    async def get_node_stats(self) -> EthstatsData:
        '''Getter for data that should be sent periodically.'''
        try:
            peer_count = (await self.wait(
                self.context.event_bus.request(
                    PeerCountRequest(),
                    TO_NETWORKING_BROADCAST_CONFIG,
                ),
                timeout=0.5
            )).peer_count
        except TimeoutError:
            self.logger.warning("Timeout: PeerPool did not answer PeerCountRequest")
            peer_count = 0

        return {
            'active': True,
            'uptime': 100,
            'peers': peer_count,
        }

    def get_chain(self) -> BaseChain:
        db_manager = create_db_manager(self.context.trinity_config.database_ipc_path)
        db_manager.connect()

        chain_config = self.context.trinity_config.get_chain_config()

        chain: BaseChain

        if self.context.trinity_config.sync_mode == SYNC_LIGHT:
            header_db = db_manager.get_headerdb()  # type: ignore
            chain = chain_config.light_chain_class(
                header_db,
                peer_chain=EventBusLightPeerChain(self.context.event_bus)
            )
        else:
            db = db_manager.get_db()  # type: ignore
            chain = chain_config.full_chain_class(db)

        return chain
