from typing import Any, cast, Dict, Union, Tuple

from cached_property import cached_property

from eth_typing import BlockNumber, Hash32

from p2p.abc import ConnectionAPI
from p2p.exchange import ExchangeAPI, ExchangeLogic
from p2p.logic import Application, CommandHandler
from p2p.qualifiers import HasProtocol
from p2p.typing import Payload

from trinity.protocol.common.abc import HeadInfoAPI

from .commands import Announce
from .handshaker import LESHandshakeReceipt
from .proto import LESProtocol, LESProtocolV2
from .exchanges import GetBlockHeadersExchange


class HeadInfoTracker(CommandHandler, HeadInfoAPI):
    command_type = Announce

    _head_td: int = None
    _head_hash: Hash32 = None
    _head_number: BlockNumber = None

    async def handle(self, connection: ConnectionAPI, msg: Payload) -> None:
        head_info = cast(Dict[str, Union[int, Hash32, BlockNumber]], msg)
        head_td = cast(int, head_info['head_td'])
        if head_td > self.head_td:
            self._head_td = head_td
            self._head_hash = cast(Hash32, head_info['head_hash'])
            self._head_number = cast(BlockNumber, head_info['head_number'])

    #
    # HeadInfoAPI
    #
    @cached_property
    def _les_receipt(self) -> LESHandshakeReceipt:
        return self.connection.get_receipt_by_type(LESHandshakeReceipt)

    @property
    def head_td(self) -> int:
        if self._head_td is None:
            self._head_td = self._les_receipt.head_td
        return self._head_td

    @property
    def head_hash(self) -> Hash32:
        if self._head_hash is None:
            self._head_hash = self._les_receipt.head_hash
        return self._head_hash

    @property
    def head_number(self) -> BlockNumber:
        if self._head_number is None:
            self._head_number = self._les_receipt.head_number
        return self._head_number


class LESAPI(Application):
    name = 'les'
    qualifier = HasProtocol(LESProtocol) | HasProtocol(LESProtocolV2)

    head_info: HeadInfoTracker

    get_block_headers: GetBlockHeadersExchange

    def __init__(self) -> None:
        self.head_info = HeadInfoTracker()
        self.add_child_behavior(self.head_info.as_behavior())

        self.get_block_headers = GetBlockHeadersExchange()
        self.add_child_behavior(ExchangeLogic(self.get_block_headers).as_behavior())

    @cached_property
    def exchanges(self) -> Tuple[ExchangeAPI[Any, Any, Any], ...]:
        return (
            self.get_block_headers,
        )

    def get_extra_stats(self) -> Tuple[str, ...]:
        return tuple(
            f"{exchange.get_response_cmd_type()}: {exchange.tracker.get_stats()}"
            for exchange in self.exchanges
        )

    @property
    def receipt(self) -> LESHandshakeReceipt:
        return self.connection.get_receipt_by_type(LESHandshakeReceipt)

    @cached_property
    def network_id(self) -> int:
        return self.receipt.network_id

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self.receipt.genesis_hash
