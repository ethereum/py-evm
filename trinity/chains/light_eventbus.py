from typing import (
    List,
)

from lahja import EndpointAPI

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

from trinity.constants import (
    TO_NETWORKING_BROADCAST_CONFIG,
)
from trinity.protocol.les.events import (
    GetBlockHeaderByHashRequest,
    GetBlockBodyByHashRequest,
    GetContractCodeRequest,
    GetAccountRequest,
    GetReceiptsRequest,

)
from trinity.rlp.block_body import BlockBody
from trinity.sync.light.service import (
    BaseLightPeerChain,
)

from trinity._utils.errors import (
    pass_or_raise,
)


class EventBusLightPeerChain(BaseLightPeerChain):
    """
    The ``EventBusLightPeerChain`` is an implementation of the ``BaseLightPeerChain`` that can
    be used from within any process.
    """

    def __init__(self, event_bus: EndpointAPI) -> None:
        self.event_bus = event_bus

    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        event = GetBlockHeaderByHashRequest(block_hash)
        return pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).block_header

    async def coro_get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        event = GetBlockBodyByHashRequest(block_hash)
        return pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).block_body

    async def coro_get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        event = GetReceiptsRequest(block_hash)
        return pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).receipts

    async def coro_get_account(self, block_hash: Hash32, address: Address) -> Account:
        event = GetAccountRequest(block_hash, address)
        return pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).account

    async def coro_get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        event = GetContractCodeRequest(block_hash, address)
        return pass_or_raise(
            await self.event_bus.request(event, TO_NETWORKING_BROADCAST_CONFIG)
        ).bytez
