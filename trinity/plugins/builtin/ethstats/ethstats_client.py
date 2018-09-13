import asyncio
import datetime
import json
import platform

import websockets

from trinity.utils.version import construct_trinity_client_identifier

class EthstatsClient:
    def __init__(self, websocket: websockets.client.WebSocketClientProtocol, node_id: str, server_url: str, server_secret: str) -> None:
        self.websocket = websocket
        self.send_queue = asyncio.Queue()

        self.node_id = node_id
        self.server_url = server_url
        self.server_secret = server_secret

        self.client = construct_trinity_client_identifier()
        self.os = platform.system()
        self.os_v = platform.release()

    async def response_handler(self) -> None:
        async for message in self.websocket:
            command, data = self.stat_recv(message)
            if command == 'node-pong':
                timestamp = round(datetime.datetime.now().timestamp() * 1000)
                latency = (timestamp - data['clientTime']) // 2
                await self.send_latency(latency)
    
    async def request_handler(self) -> None:
        while True:
            message = await self.send_queue.get()
            [command, data] = message
            await self.stat_send(command, data)

    async def connection_handler(self) -> None:
        consumer_task = asyncio.ensure_future(self.response_handler())
        producer_task = asyncio.ensure_future(self.request_handler())

        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    async def stat_send(self, command: str, data: dict) -> None:
        message = {'emit': [
            command,
            {**data, 'id': self.node_id},
        ]}

        await self.websocket.send(json.dumps(message))

    def stat_recv(self, message) -> (str, dict):
        try:
            response = json.loads(message)
        except json.decoder.JSONDecodeError as e:
            self.logger.error(f'Failed to parse stats server message: {e.msg}.')
            return

        try:
            payload = response['emit']
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
        await self.send_queue.put(['hello', {
            'info': {
                'name': '#some_name',
                'contact': '#some_contact',
                'os': self.os,
                'os_v': self.os_v,
                'client': self.client,
                'canUpdateHistory': True,
            },
            'secret': self.server_secret,
        }])

    async def send_latency(self, latency) -> None:
        await self.send_queue.put(['latency', {
            'latency': latency,
        }])

    async def send_history(self) -> None:
        await self.send_queue.put(['history', {
            'history': {},
        }])

    async def send_block(self, block) -> None:
        await self.send_queue.put(['block', {
            'block': block,
        }])

    async def send_pending(self) -> None:
        await self.send_queue.put(['pending', {
            'stats': {
                'pending': 0,
            },
        }])

    async def send_stats(self, stats) -> None:
        await self.send_queue.put(['stats', {
            'stats': stats,
        }])

    async def send_node_ping(self) -> None:
        timestamp = round(datetime.datetime.now().timestamp() * 1000)

        await self.send_queue.put(['node-ping', {
            'clientTime': timestamp,
        }])
