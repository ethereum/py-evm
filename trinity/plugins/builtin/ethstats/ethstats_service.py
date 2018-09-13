import asyncio

import websockets

from p2p.service import (
    BaseService
)

from trinity.plugins.builtin.ethstats.ethstats_client import (
    EthstatsClient,
)
from eth.chains.base import (
    BaseChain
)
from p2p.peer import (
    PeerPool
)


class EthstatsService(BaseService):
    def __init__(
        self,
        server_url: str,
        server_secret: str,
        chain: BaseChain,
        peer_pool: PeerPool,
        *args,
        **kwargs
    ) -> None:
        super(EthstatsService, self).__init__(*args, **kwargs)

        self.server_url: str = server_url
        self.server_secret: str = server_secret

        self.chain: BaseChain = chain
        self.peer_pool: PeerPool = peer_pool

    async def _run(self) -> None:
        await self.connection_loop()

    async def connection_loop(self) -> None:
        while self.is_operational:
            try:
                self.logger.info(f'Connecting to {self.server_url}...')
                async with websockets.connect(self.server_url) as websocket:
                    client = EthstatsClient(websocket, '#node_id', self.server_url, self.server_secret)
                    
                    done, pending = await asyncio.wait(
                        [
                            asyncio.ensure_future(client.connection_handler()),
                            asyncio.ensure_future(self.statistics_handler(client)),
                        ],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

            except websockets.ConnectionClosed as e:
                self.logger.warning(f'Connection to {self.server_url} is closed - code: {e.code}, reason: {e.reason}.')

            self.logger.info('Reconnecting in 5s...')
            await self.sleep(5)

    async def statistics_handler(self, client) -> None:
        await client.send_hello()
        # await client.send_history()
        await client.send_pending()

        while self.is_operational:
            block = self.chain.get_canonical_head()
            peers = len(self.peer_pool)

            await client.send_node_ping()
            await client.send_stats({
                'active': True,
                'peers': peers,
            })
            await client.send_block({
                'number': block.block_number,
                'hash': block.hex_hash,
                'uncles': 0,
                'transactions': 0,
                'difficulty': 0,
            })
            await self.sleep(5)