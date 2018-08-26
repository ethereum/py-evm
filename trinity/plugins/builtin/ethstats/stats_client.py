import asyncio
import json

from datetime import datetime

import websockets

from p2p.service import (
    BaseService
)


class StatsClient(BaseService):
    def __init__(self, stats_server_url: str, stats_server_secret: str, *args, **kwargs) -> None:
        super(StatsClient, self).__init__(*args, **kwargs)

        self.stats_server_url = stats_server_url
        self.stats_server_secret = stats_server_secret

        self.node_id = '#some_id'

    async def _run(self) -> None:
        await self.connection_loop()

    async def connection_loop(self) -> None:
        while True:
            try:
                self.logger.info('Connecting...')
                async with websockets.connect(self.stats_server_url) as websocket:
                    self.websocket = websocket
                    await self.connection_handler()
            except websockets.ConnectionClosed as e:
                self.logger.warning(f'Connection is closed - code: {e.code}, reason: {e.reason}.')

            self.logger.info('Reconnecting in 5s...')
            await asyncio.sleep(5)

    async def connection_handler(self) -> None:
        await self.send_hello()

        await self.send_latency()
        # await self.send_history()
        await self.send_block()
        await self.send_pending()
        await self.send_node_ping()

        while True:
            await self.send_stats()
            await asyncio.sleep(3)

    async def stat_send(self, command: str, data: dict) -> None:
        message = {'emit': [
            command,
            {**data, 'id': self.node_id},
        ]}

        await self.websocket.send(json.dumps(message))

    async def stat_recv(self) -> (str, dict):
        try:
            message = json.loads(await self.websocket.recv())
        except json.decoder.JSONDecodeError as e:
            self.logger.error(f'Failed to parse stats server message: {e.msg}.')
            return

        try:
            payload = message['emit']
        except KeyError:
            self.logger.error(f'Invalid stats server message format.')
            return

        if len(payload) == 1:
            command, = payload
            data = None
        elif len(payload) == 2:
            command, data = payload
        else:
            self.logger.error(f'Invalid stats server message content.')
            return

        return command, data

    async def send_hello(self) -> None:
        await self.stat_send('hello', {
            'info': {
                'name': '#some_name',
                'contact': '#some_contact',
                'os': '#some_os',
                'os_v': '#some_os_version',
                'client': '#some_client',
                'canUpdateHistory': True,
            },
            'secret': self.stats_server_secret,
        })

    async def send_latency(self) -> None:
        await self.stat_send('latency', {
            'latency': 404,
        })

    async def send_history(self) -> None:
        await self.stat_send('history', {
            'history': {},
        })

    async def send_block(self) -> None:
        await self.stat_send('block', {
            'block': {},
        })

    async def send_pending(self) -> None:
        await self.stat_send('pending', {
            'stats': {
                'pending': {},
            },
        })

    async def send_stats(self) -> None:
        await self.stat_send('stats', {
            'stats': {
                'active': True,
                'peers': 42,
                'mining': 24,
            },
        })

    async def send_node_ping(self) -> None:
        timestamp = round(datetime.now().timestamp() * 1000)

        await self.stat_send('node-ping', {
            'clientTime': timestamp,
        })
