import asyncio
from enum import (
    auto,
    Enum,
)
import inspect
from typing import (
    Any,
    Callable,
    Generic,
    List,
)
from eth_typing import (
    Address,
    Hash32,
)

from eth.rlp.accounts import (
    Account,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.receipts import (
    Receipt,
)

from lahja import (
    BaseEvent,
    Endpoint,
)
from trinity.rlp.block_body import BlockBody
from trinity.sync.light.service import (
    BaseLightPeerChain,
)


class LightPeerChainRequest(BaseEvent):

    def __init__(self, method_name: str, payload: Any = None) -> None:
        self.method_name = method_name
        self.payload = payload


class LightPeerChainResponse(BaseEvent):

    def __init__(self, payload: Any = None) -> None:
        self.payload = payload


class LightPeerChainEventBusResponder:

    def __init__(self, chain: BaseLightPeerChain, event_bus: Endpoint) -> None:
        self.chain = chain
        self.event_bus = event_bus
        asyncio.ensure_future(self.answer_requests())

    async def answer_requests(self) -> None:
        async for event in self.event_bus.stream(LightPeerChainRequest):

            method = getattr(self.chain, event.method_name)

            if not callable(method):
                self.event_bus.broadcast(
                    LightPeerChainResponse(Exception(f"Not a method: {event.method_name}")), event.broadcast_config()
                )
                continue

            try:
                if event.payload is not None:
                    response = await method(*event.payload)
                else:
                    response = await method()
            except Exception as e:
                # we send the exception over to raise it on the other end
                self.event_bus.broadcast(LightPeerChainResponse(e), event.broadcast_config())
            else:
                self.event_bus.broadcast(LightPeerChainResponse(response), event.broadcast_config())


class EventBusLightPeerChain:

    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    async def get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    async def get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    async def get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    async def get_foo(self) -> BlockHeader:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))


    async def get_foobar(self, foo: int, bar: int) -> BlockHeader:
        event = self.prepare_event(inspect.currentframe())
        return self.return_or_raise(await self.event_bus.request(event))

    def return_or_raise(self, response: LightPeerChainResponse):
        if issubclass(type(response.payload), Exception):
            raise Exception("Something bad happened in the other process", response.payload) from response.payload

        return response.payload

    def prepare_event(self, frame):
        args = tuple(self.args_without_self(frame.f_locals.values()))
        fn_name = frame.f_code.co_name

        payload = None if len(args) == 0 else args

        return LightPeerChainRequest(fn_name, args)

    def args_without_self(self, loco):
        for val in loco:
            if val is not self:
                yield val