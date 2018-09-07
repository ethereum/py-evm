import asyncio
from enum import (
    auto,
    Enum,
)
from typing import (
    Any,
)
from eth_typing import (
    Hash32,
)

from eth.rlp.headers import (
    BlockHeader,
)
from lahja import (
    BaseEvent,
    Endpoint,
)
from trinity.rlp.block_body import BlockBody
from trinity.sync.light.service import (
    LightPeerChain,
)


# This is an ad-hoc PoC attempt. I'm sure we can use some meta programming magic
# to make this whole thing effectively become zero maintanance (e.g. new / changed
# APIs in LightPeerChain are automatically accessible through event-bus calls)
class LightPeerChainAPI:

    GET_BLOCK_HEADER_BY_HASH = 'get_block_header_by_hash'
    GET_BLOCK_BODY_BY_HASH = 'get_block_body_by_hash'
    GET_FOOBAR = 'get_foobar'

class LightPeerChainRequest(BaseEvent):

    def __init__(self, api: LightPeerChainAPI, payload: Any = None):
        self.api = api
        self.payload = payload

class LightPeerChainResponse(BaseEvent):

    def __init__(self, payload: Any = None):
        self.payload = payload



class LightPeerChainEventBusBridge:

    def __init__(self, chain: LightPeerChain, event_bus: Endpoint):
        self.chain = chain
        self.event_bus = event_bus
        asyncio.ensure_future(self.answer_requests())

    async def answer_requests(self) -> None:
        async for event in self.event_bus.stream(LightPeerChainRequest):

            method = getattr(self.chain, event.api)

            if not callable(method):
                self.event_bus.broadcast(
                    LightPeerChainResponse(Exception(f"Not a method: {event.api}")), event.broadcast_config()
                )
                continue

            try:
                response = await method(*event.payload)
            except Exception as e:
                # we send the exception over to raise it on the other end
                self.event_bus.broadcast(LightPeerChainResponse(e), event.broadcast_config())
            else:
                self.event_bus.broadcast(LightPeerChainResponse(response), event.broadcast_config())


class EventBusLightPeerChain:

    def __init__(self, event_bus: Endpoint):
        self.event_bus = event_bus

    # TODO: We can generate all the functions that exist on the remote `LightPeerChain`
    # effectively making this approach zero maintanance in the sense that if methods change
    # or are added on `LightPeerChain`, they will automaticaly be usable on the `EventBusLightPeerChain`
    # as well

    async def get_block_header_by_hash(self) -> BlockHeader:
        response = await self.event_bus.request(
            LightPeerChainRequest(LightPeerChainAPI.GET_BLOCK_HEADER_BY_HASH, (b'test',))
        )
        self.raise_on_error(response)

        return response.payload.is_genesis

    async def get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:

        response = await self.event_bus.request(
            LightPeerChainRequest(LightPeerChainAPI.GET_BLOCK_BODY_BY_HASH, (block_hash,))
        )

        self.raise_on_error(response)

        return response.payload

    async def get_foo(self) -> BlockHeader:
        response = await self.event_bus.request(
            LightPeerChainRequest(LightPeerChainAPI.GET_FOOBAR, (1, 2,))
        )

        self.raise_on_error(response)

        return response.payload

    def raise_on_error(self, response: LightPeerChainResponse) -> None:
        if issubclass(type(response.payload), Exception):
            raise Exception("Something bad happened in the other process", response.payload) from response.payload
