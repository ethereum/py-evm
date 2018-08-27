import asyncio
import logging
from typing import (
    Any,
    Dict,
)
from lahja import (
    Endpoint
)

from trinity.events import (
    PeerCountRequest,
)
from trinity.extensibility import (
    BaseOwnProcessPlugin,
)


async def request_receive_peer_count(event_bus: Endpoint) -> None:
    while True:
        response = await event_bus.request(PeerCountRequest())
        print("Peer Count: " + str(response.payload))
        await asyncio.sleep(1)


class ProcTest(BaseOwnProcessPlugin):

    def __init__(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "ProcTest"

    def should_start(self) -> bool:
        return True

    @staticmethod
    def launch_process(event_bus: Endpoint, **kwargs: Dict[str, Any]) -> None:
        logger = logging.getLogger('FOOBAR')
        logger.info('hello from test proc')
        loop = asyncio.get_event_loop()
        event_bus.connect()

        asyncio.ensure_future(request_receive_peer_count(event_bus))
        loop.run_forever()
        loop.close()
