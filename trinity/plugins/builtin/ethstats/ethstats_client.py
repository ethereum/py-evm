import datetime
import json
import platform

import websockets

from trinity.utils.version import construct_trinity_client_identifier

class EthstatsClient:
    def __init__(self, websocket: websockets.client.WebSocketClientProtocol, node_id: str, server_url: str, server_secret: str) -> None:
        self.websocket = websocket

        self.node_id = node_id
        self.server_url = server_url
        self.server_secret = server_secret

        self.client = construct_trinity_client_identifier()
        self.os = platform.system()
        self.os_v = platform.release()

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
                'os': self.os,
                'os_v': self.os_v,
                'client': self.client,
                'canUpdateHistory': True,
            },
            'secret': self.server_secret,
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
                'pending': 0,
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
        timestamp = round(datetime.datetime.now().timestamp() * 1000)

        await self.stat_send('node-ping', {
            'clientTime': timestamp,
        })
