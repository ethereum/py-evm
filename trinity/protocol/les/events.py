from dataclasses import (
    dataclass,
)
from typing import (
    List,
    Tuple,
    Type,
)

from eth.rlp.accounts import Account
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth_typing import (
    Address,
    Hash32,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)
from p2p.kademlia import Node

from trinity.protocol.common.events import (
    PeerPoolMessageEvent,
)
from trinity.rlp.block_body import BlockBody


@dataclass
class BlockHeaderResponse(BaseEvent):

    block_header: BlockHeader
    error: Exception = None


@dataclass
class BlockBodyResponse(BaseEvent):

    block_body: BlockBody
    error: Exception = None


@dataclass
class ReceiptsResponse(BaseEvent):

    receipts: List[Receipt]
    error: Exception = None


@dataclass
class AccountResponse(BaseEvent):

    account: Account
    error: Exception = None


@dataclass
class BytesResponse(BaseEvent):

    bytez: bytes
    error: Exception = None


@dataclass
class GetBlockHeaderByHashRequest(BaseRequestResponseEvent[BlockHeaderResponse]):

    block_hash: Hash32

    @staticmethod
    def expected_response_type() -> Type[BlockHeaderResponse]:
        return BlockHeaderResponse


@dataclass
class GetBlockBodyByHashRequest(BaseRequestResponseEvent[BlockBodyResponse]):

    block_hash: Hash32

    @staticmethod
    def expected_response_type() -> Type[BlockBodyResponse]:
        return BlockBodyResponse


@dataclass
class GetReceiptsRequest(BaseRequestResponseEvent[ReceiptsResponse]):

    block_hash: Hash32

    @staticmethod
    def expected_response_type() -> Type[ReceiptsResponse]:
        return ReceiptsResponse


@dataclass
class GetAccountRequest(BaseRequestResponseEvent[AccountResponse]):

    block_hash: Hash32
    address: Address

    @staticmethod
    def expected_response_type() -> Type[AccountResponse]:
        return AccountResponse


@dataclass
class GetContractCodeRequest(BaseRequestResponseEvent[BytesResponse]):

    block_hash: Hash32
    address: Address

    @staticmethod
    def expected_response_type() -> Type[BytesResponse]:
        return BytesResponse


class GetBlockHeadersEvent(PeerPoolMessageEvent):
    """
    Event to carry a ``GetBlockHeaders`` command from the peer pool to any process that
    subscribes the event through the event bus.
    """
    pass


@dataclass
class SendBlockHeadersEvent(BaseEvent):
    """
    Event to proxy a ``LESPeer.sub_proto.send_block_heades`` call from a proxy peer to the actual
    peer that sits in the peer pool.
    """
    remote: Node
    headers: Tuple[BlockHeader, ...]
    buffer_value: int
    request_id: int
