from typing import (
    List,
    Type,
    TypeVar,
)

from cancel_token import (
    CancelToken,
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
    BaseRequestResponseEvent,
)
from p2p.service import (
    BaseService,
)

from trinity.constants import (
    TO_NETWORKING_BROADCAST_CONFIG,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity._utils.async_errors import (
    await_and_wrap_errors,
)
from trinity.rlp.block_body import BlockBody
from trinity.sync.light.service import (
    BaseLightPeerChain,
)


class BaseLightPeerChainResponse(BaseEvent):

    def __init__(self, error: Exception) -> None:
        self.error = error


class BlockHeaderResponse(BaseLightPeerChainResponse):

    def __init__(self, block_header: BlockHeader, error: Exception=None) -> None:
        super().__init__(error)
        self.block_header = block_header


class BlockBodyResponse(BaseLightPeerChainResponse):

    def __init__(self, block_body: BlockBody, error: Exception=None) -> None:
        super().__init__(error)
        self.block_body = block_body


class ReceiptsResponse(BaseLightPeerChainResponse):

    def __init__(self, receipts: List[Receipt], error: Exception=None) -> None:
        super().__init__(error)
        self.receipts = receipts


class AccountResponse(BaseLightPeerChainResponse):

    def __init__(self, account: Account, error: Exception=None) -> None:
        super().__init__(error)
        self.account = account


class BytesResponse(BaseLightPeerChainResponse):

    def __init__(self, bytez: bytes, error: Exception=None) -> None:
        super().__init__(error)
        self.bytez = bytez


class GetBlockHeaderByHashRequest(BaseRequestResponseEvent[BlockHeaderResponse]):

    def __init__(self, block_hash: Hash32) -> None:
        self.block_hash = block_hash

    @staticmethod
    def expected_response_type() -> Type[BlockHeaderResponse]:
        return BlockHeaderResponse


class GetBlockBodyByHashRequest(BaseRequestResponseEvent[BlockBodyResponse]):

    def __init__(self, block_hash: Hash32) -> None:
        self.block_hash = block_hash

    @staticmethod
    def expected_response_type() -> Type[BlockBodyResponse]:
        return BlockBodyResponse


class GetReceiptsRequest(BaseRequestResponseEvent[ReceiptsResponse]):

    def __init__(self, block_hash: Hash32) -> None:
        self.block_hash = block_hash

    @staticmethod
    def expected_response_type() -> Type[ReceiptsResponse]:
        return ReceiptsResponse


class GetAccountRequest(BaseRequestResponseEvent[AccountResponse]):

    def __init__(self, block_hash: Hash32, address: Address) -> None:
        self.block_hash = block_hash
        self.address = address

    @staticmethod
    def expected_response_type() -> Type[AccountResponse]:
        return AccountResponse


class GetContractCodeRequest(BaseRequestResponseEvent[BytesResponse]):

    def __init__(self, block_hash: Hash32, address: Address) -> None:
        self.block_hash = block_hash
        self.address = address

    @staticmethod
    def expected_response_type() -> Type[BytesResponse]:
        return BytesResponse


class LightPeerChainEventBusHandler(BaseService):
    """
    The ``LightPeerChainEventBusHandler`` listens for certain events on the eventbus and
    delegates them to the ``LightPeerChain`` to get answers. It then propagates responses
    back to the caller.
    """

    def __init__(self,
                 chain: BaseLightPeerChain,
                 event_bus: TrinityEventBusEndpoint,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.chain = chain
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.logger.info("Running LightPeerChainEventBusHandler")

        self.run_daemon_task(self.handle_get_blockheader_by_hash_requests())
        self.run_daemon_task(self.handle_get_blockbody_by_hash_requests())
        self.run_daemon_task(self.handle_get_receipts_by_hash_requests())
        self.run_daemon_task(self.handle_get_account_requests())
        self.run_daemon_task(self.handle_get_contract_code_requests())

    async def handle_get_blockheader_by_hash_requests(self) -> None:
        async for event in self.event_bus.stream(GetBlockHeaderByHashRequest):

            val, error = await await_and_wrap_errors(
                self.chain.coro_get_block_header_by_hash(event.block_hash)
            )

            await self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )

    async def handle_get_blockbody_by_hash_requests(self) -> None:
        async for event in self.event_bus.stream(GetBlockBodyByHashRequest):

            val, error = await await_and_wrap_errors(
                self.chain.coro_get_block_body_by_hash(event.block_hash)
            )

            await self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )

    async def handle_get_receipts_by_hash_requests(self) -> None:
        async for event in self.event_bus.stream(GetReceiptsRequest):

            val, error = await await_and_wrap_errors(self.chain.coro_get_receipts(event.block_hash))

            await self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )

    async def handle_get_account_requests(self) -> None:
        async for event in self.event_bus.stream(GetAccountRequest):

            val, error = await await_and_wrap_errors(
                self.chain.coro_get_account(event.block_hash, event.address)
            )

            await self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )

    async def handle_get_contract_code_requests(self) -> None:

        async for event in self.event_bus.stream(GetContractCodeRequest):

            val, error = await await_and_wrap_errors(
                self.chain.coro_get_contract_code(event.block_hash, event.address)
            )

            await self.event_bus.broadcast(
                event.expected_response_type()(val, error),
                event.broadcast_config()
            )


class EventBusLightPeerChain(BaseLightPeerChain):
    """
    The ``EventBusLightPeerChain`` is an implementation of the ``BaseLightPeerChain`` that can
    be used from within any process.
    """

    def __init__(self, event_bus: TrinityEventBusEndpoint) -> None:
        self.event_bus = event_bus

    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        event = GetBlockHeaderByHashRequest(block_hash)
        return self._pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).block_header

    async def coro_get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        event = GetBlockBodyByHashRequest(block_hash)
        return self._pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).block_body

    async def coro_get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        event = GetReceiptsRequest(block_hash)
        return self._pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).receipts

    async def coro_get_account(self, block_hash: Hash32, address: Address) -> Account:
        event = GetAccountRequest(block_hash, address)
        return self._pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).account

    async def coro_get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        event = GetContractCodeRequest(block_hash, address)
        return self._pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).bytez

    TResponse = TypeVar("TResponse", bound=BaseLightPeerChainResponse)

    def _pass_or_raise(self, response: TResponse) -> TResponse:
        if response.error is not None:
            raise response.error

        return response
