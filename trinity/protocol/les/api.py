from abc import abstractmethod
from typing import (
    Any,
    Generic,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from cached_property import cached_property

from eth.abc import BlockHeaderAPI
from eth_typing import BlockNumber, Hash32
from eth_utils import ValidationError

from p2p.abc import ConnectionAPI
from p2p.exchange import ExchangeAPI, ExchangeLogic
from p2p.logic import Application, CommandHandler
from p2p.qualifiers import HasProtocol

from trinity._utils.les import gen_request_id
from trinity.protocol.common.abc import HeadInfoAPI

from .constants import (
    MAX_BODIES_FETCH,
    MAX_HEADERS_FETCH,
    MAX_RECEIPTS_FETCH,
)
from .commands import (
    Announce,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetContractCodes,
    GetReceipts,
)
from .exchanges import GetBlockHeadersExchange
from .handshaker import LESHandshakeReceipt
from .payloads import (
    AnnouncePayload,
    BlockHeadersPayload,
    BlockHeadersQuery,
    GetBlockBodiesPayload,
    GetBlockHeadersPayload,
    GetContractCodesPayload,
    GetProofsPayload,
    GetReceiptsPayload,
    StatusPayload,
    ContractCodeRequest,
    ProofRequest,
)
from .proto import BaseLESProtocol, LESProtocolV1, LESProtocolV2


class HeadInfoTracker(CommandHandler[Announce], HeadInfoAPI):
    command_type = Announce

    _head_td: int = None
    _head_hash: Hash32 = None
    _head_number: BlockNumber = None

    async def handle(self, connection: ConnectionAPI, cmd: Announce) -> None:
        if cmd.payload.head_td > self.head_td:
            self._head_td = cmd.payload.head_td
            self._head_hash = cmd.payload.head_hash
            self._head_number = cmd.payload.head_number

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


TLESProtocol = TypeVar('TLESProtocol', bound=BaseLESProtocol)


class BaseLESAPI(Application, Generic[TLESProtocol]):
    name = 'les'

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
    @abstractmethod
    def protocol(self) -> TLESProtocol:
        ...

    @cached_property
    def receipt(self) -> LESHandshakeReceipt:
        return self.connection.get_receipt_by_type(LESHandshakeReceipt)

    @cached_property
    def network_id(self) -> int:
        return self.receipt.network_id

    @cached_property
    def genesis_hash(self) -> Hash32:
        return self.receipt.genesis_hash

    def send_status(self, payload: StatusPayload) -> None:
        if payload.version != self.protocol.version:
            raise ValidationError(
                f"LES protocol version mismatch: "
                f"params:{payload.version} != proto:{self.protocol.version}"
            )
        self.protocol.send(self.protocol.status_command_type(payload))

    def send_announce(self,
                      header: BlockHeaderAPI,
                      head_td: int,
                      reorg_depth: int = 0,
                      params: Sequence[Tuple[str, bytes]] = ()) -> None:
        payload = AnnouncePayload(
            head_hash=header.hash,
            head_number=header.block_number,
            head_td=head_td,
            reorg_depth=reorg_depth,
            params=tuple(params),
        )
        self.protocol.send(Announce(payload))

    def send_get_block_bodies(self, block_hashes: Sequence[Hash32]) -> int:
        if len(block_hashes) > MAX_BODIES_FETCH:
            raise ValueError(
                f"Cannot ask for more than {MAX_BODIES_FETCH} blocks in a single request"
            )
        payload = GetBlockBodiesPayload(
            request_id=gen_request_id(),
            block_hashes=tuple(block_hashes),
        )
        self.protocol.send(GetBlockBodies(payload))
        return payload.request_id

    def send_get_block_headers(
            self,
            block_number_or_hash: Union[BlockNumber, Hash32],
            max_headers: int,
            skip: int,
            reverse: bool) -> int:
        if max_headers > MAX_HEADERS_FETCH:
            raise ValidationError(
                f"Cannot ask for more than {MAX_HEADERS_FETCH} headers in a single request"
            )
        query = BlockHeadersQuery(
            block_number_or_hash=block_number_or_hash,
            max_headers=max_headers,
            skip=skip,
            reverse=reverse,
        )
        payload = GetBlockHeadersPayload(
            request_id=gen_request_id(),
            query=query,
        )
        self.protocol.send(GetBlockHeaders(payload))
        return payload.request_id

    def send_block_headers(
            self,
            headers: Sequence[BlockHeaderAPI],
            buffer_value: int = 0,
            request_id: int = None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        payload = BlockHeadersPayload(
            request_id=request_id,
            buffer_value=buffer_value,
            headers=tuple(headers),
        )
        self.protocol.send(BlockHeaders(payload))
        return payload.request_id

    def send_get_receipts(self, block_hashes: Sequence[Hash32]) -> int:
        if len(block_hashes) > MAX_RECEIPTS_FETCH:
            raise ValidationError(
                f"Cannot ask for more than {MAX_RECEIPTS_FETCH} receipts in a single request"
            )
        payload = GetReceiptsPayload(
            request_id=gen_request_id(),
            block_hashes=tuple(block_hashes),
        )
        self.protocol.send(GetReceipts(payload))
        return payload.request_id

    def send_get_proof(self,
                       block_hash: Hash32,
                       state_key: Hash32,
                       storage_key: Optional[Hash32],
                       from_level: int) -> int:
        proof_request = ProofRequest(
            block_hash=block_hash,
            storage_key=storage_key,
            state_key=state_key,
            from_level=from_level
        )
        return self.send_get_proofs(proof_request)

    def send_get_proofs(self, *proofs: ProofRequest) -> int:
        payload = GetProofsPayload(
            request_id=gen_request_id(),
            proofs=proofs,
        )
        self.protocol.send(self.protocol.get_proofs_command_type(payload))
        return payload.request_id

    def send_get_contract_code(self, block_hash: Hash32, account: Hash32) -> int:
        request = ContractCodeRequest(block_hash=block_hash, account=account)
        return self.send_get_contract_codes(request)

    def send_get_contract_codes(self, *code_requests: ContractCodeRequest) -> int:
        payload = GetContractCodesPayload(
            request_id=gen_request_id(),
            code_requests=code_requests,
        )
        self.protocol.send(GetContractCodes(payload))
        return payload.request_id


class LESV1API(BaseLESAPI[LESProtocolV1]):
    qualifier = HasProtocol(LESProtocolV1)

    @cached_property
    def protocol(self) -> LESProtocolV1:
        return self.connection.get_protocol_by_type(LESProtocolV1)


class LESV2API(BaseLESAPI[LESProtocolV2]):
    qualifier = HasProtocol(LESProtocolV2)

    @cached_property
    def protocol(self) -> LESProtocolV2:
        return self.connection.get_protocol_by_type(LESProtocolV2)
