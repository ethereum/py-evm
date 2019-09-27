from typing import cast, Any, Dict, Tuple

from cached_property import cached_property

from eth_typing import BlockNumber, Hash32

from p2p.abc import ConnectionAPI
from p2p.exchange import ExchangeAPI, ExchangeLogic
from p2p.logic import Application, CommandHandler
from p2p.qualifiers import HasProtocol
from p2p.typing import Payload

from trinity.protocol.common.abc import HeadInfoAPI

from .commands import NewBlock
from .exchanges import (
    GetBlockBodiesExchange,
    GetBlockHeadersExchange,
    GetNodeDataExchange,
    GetReceiptsExchange,
)
from .handshaker import ETHHandshakeReceipt
from .proto import ETHProtocol


class HeadInfoTracker(CommandHandler, HeadInfoAPI):
    command_type = NewBlock

    _head_td: int = None
    _head_hash: Hash32 = None
    _head_number: BlockNumber = None

    async def handle(self, connection: ConnectionAPI, msg: Payload) -> None:
        msg = cast(Dict[str, Any], msg)
        header, _, _ = msg['block']
        actual_td = msg['total_difficulty'] - header.difficulty

        if actual_td > self.head_td:
            self._head_hash = header.parent_hash
            self._head_td = actual_td
            self._head_number = header.block_number - 1

    #
    # HeadInfoAPI
    #
    @cached_property
    def _eth_receipt(self) -> ETHHandshakeReceipt:
        return self.connection.get_receipt_by_type(ETHHandshakeReceipt)

    @property
    def head_td(self) -> int:
        if self._head_td is None:
            self._head_td = self._eth_receipt.total_difficulty
        return self._head_td

    @property
    def head_hash(self) -> Hash32:
        if self._head_hash is None:
            self._head_hash = self._eth_receipt.head_hash
        return self._head_hash

    @property
    def head_number(self) -> BlockNumber:
        if self._head_number is None:
            # TODO: fetch on demand using request/response API
            raise AttributeError("Head block number is not currently known")
        return self._head_number


class ETHAPI(Application):
    name = 'eth'
    qualifier = HasProtocol(ETHProtocol)

    head_info: HeadInfoTracker

    get_block_bodies: GetBlockBodiesExchange
    get_block_headers: GetBlockHeadersExchange
    get_node_data: GetNodeDataExchange
    get_receipts: GetReceiptsExchange

    def __init__(self) -> None:
        self.head_info = HeadInfoTracker()
        self.add_child_behavior(self.head_info.as_behavior())

        # Request/Response API
        self.get_block_bodies = GetBlockBodiesExchange()
        self.get_block_headers = GetBlockHeadersExchange()
        self.get_node_data = GetNodeDataExchange()
        self.get_receipts = GetReceiptsExchange()

        self.add_child_behavior(ExchangeLogic(self.get_block_bodies).as_behavior())
        self.add_child_behavior(ExchangeLogic(self.get_block_headers).as_behavior())
        self.add_child_behavior(ExchangeLogic(self.get_node_data).as_behavior())
        self.add_child_behavior(ExchangeLogic(self.get_receipts).as_behavior())

    @cached_property
    def exchanges(self) -> Tuple[ExchangeAPI[Any, Any, Any], ...]:
        return (
            self.get_block_bodies,
            self.get_block_headers,
            self.get_node_data,
            self.get_receipts,
        )

    def get_extra_stats(self) -> Tuple[str, ...]:
        return tuple(
            f"{exchange.get_response_cmd_type()}: {exchange.tracker.get_stats()}"
            for exchange in self.exchanges
        )

    @cached_property
    def receipt(self) -> ETHHandshakeReceipt:
        return self.connection.get_receipt_by_type(ETHHandshakeReceipt)

    @cached_property
    def network_id(self) -> int:
        return self.receipt.network_id

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self.receipt.genesis_hash
