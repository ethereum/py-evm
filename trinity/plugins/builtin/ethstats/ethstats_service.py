import asyncio
import datetime
import json

import websockets

from p2p.service import (
    BaseService
)

from trinity.plugins.builtin.ethstats.ethstats_client import (
    EthstatsClient,
)


class StatsClient(BaseService):
    def __init__(self, stats_server_url: str, stats_server_secret: str, *args, **kwargs) -> None:
        super(StatsClient, self).__init__(*args, **kwargs)

        self.stats_server_url = stats_server_url
        self.stats_server_secret = stats_server_secret

    async def _run(self) -> None:
        await self.connection_loop()

    async def connection_loop(self) -> None:
        while self.is_operational:
            try:
                self.logger.info(f'Connecting to {self.stats_server_url}...')
                async with websockets.connect(self.stats_server_url) as websocket:
                    client = EthstatsClient(websocket, '#node_id', self.stats_server_url, self.stats_server_secret)
                    await self.connection_handler(client)
            except websockets.ConnectionClosed as e:
                self.logger.warning(f'Connection to {self.stats_server_url} is closed - code: {e.code}, reason: {e.reason}.')

            self.logger.info('Reconnecting in 5s...')
            await self.sleep(5)

    async def connection_handler(self, client: EthstatsClient) -> None:
        await client.send_hello()

        await client.send_latency()
        # await client.send_history()
        await client.send_block()
        await client.send_pending()
        await client.send_node_ping()

        while self.is_operational:
            await client.send_stats()
            await client.sleep(3)

