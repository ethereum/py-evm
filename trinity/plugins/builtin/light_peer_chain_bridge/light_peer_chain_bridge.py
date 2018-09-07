import asyncio
import inspect
from types import (
    FrameType
)
from typing import (
    Any,
    Iterable,
    List,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth_utils import (
    to_tuple,
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
    """
    The ``LightPeerChainEventBusResponder`` listens for certain events on the eventbus and
    delegates them to the ``LightPeerChain`` to get answers. It then propagates responses
    back to the caller.
    """

    def __init__(self, chain: BaseLightPeerChain, event_bus: Endpoint) -> None:
        self.chain = chain
        self.event_bus = event_bus
        asyncio.ensure_future(self.answer_requests())

    async def answer_requests(self) -> None:
        async for event in self.event_bus.stream(LightPeerChainRequest):

            method = getattr(self.chain, event.method_name)

            if not callable(method):
                self.event_bus.broadcast(
                    LightPeerChainResponse(Exception(f"Not a method: {event.method_name}")),
                    event.broadcast_config()
                )
                continue

            try:
                if event.payload is not None:
                    response = await method(*event.payload)
                else:
                    response = await method()
            except Exception as e:
                # we send the exception over to re-raise it on the consumer side (other process)
                self.event_bus.broadcast(
                    LightPeerChainResponse(e),
                    event.broadcast_config()
                )
            else:
                self.event_bus.broadcast(
                    LightPeerChainResponse(response),
                    event.broadcast_config()
                )


class EventBusLightPeerChain(BaseLightPeerChain):
    """
    The ``EventBusLightPeerChain`` is an implementation of the ``BaseLightPeerChain`` that can
    be used from within any process.
    """

    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_foo(self) -> BlockHeader:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    async def get_foobar(self, foo: int, bar: int) -> BlockHeader:
        event = self._prepare_event(inspect.currentframe())
        return self._return_or_raise(await self.event_bus.request(event))

    def _return_or_raise(self, response: LightPeerChainResponse) -> Any:
        if issubclass(type(response.payload), Exception):
            raise Exception(
                "Exception raised in LightPeerChain", response.payload
            ) from response.payload

        return response.payload

    def _prepare_event(self, frame: FrameType) -> LightPeerChainRequest:
        args = self._extract_args(frame.f_locals.values())
        fn_name = frame.f_code.co_name

        payload = None if len(args) == 0 else args

        return LightPeerChainRequest(fn_name, payload)

    @to_tuple
    def _extract_args(self, args: Iterable[Any]) -> Iterable[Any]:
        for arg in args:
            if arg is not self:
                yield arg
