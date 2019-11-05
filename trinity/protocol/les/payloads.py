from typing import (
    Any,
    cast,
    Iterable,
    NamedTuple,
    Optional,
    Tuple,
)

from eth_typing import BlockNumber, Hash32
from eth_utils import to_tuple
from mypy_extensions import TypedDict

from eth.abc import BlockHeaderAPI, ReceiptAPI

from trinity.protocol.common.payloads import BlockHeadersQuery
from trinity.rlp.block_body import BlockBody


_StatusPayloadDict = TypedDict(
    '_StatusPayloadDict',
    {
        'protocolVersion': int,
        'networkId': int,
        'headTd': int,
        'headHash': Hash32,
        'headNum': BlockNumber,
        'genesisHash': Hash32,
        'serveHeaders': bool,
        'serveChainSince': Optional[BlockNumber],
        'serveStateSince': Optional[BlockNumber],
        'serveRecentState': Optional[bool],
        'serveRecentChain': Optional[bool],
        'txRelay': bool,
        'flowControl/BL': Optional[int],
        'flowControl/MRC': Optional[Tuple[Tuple[int, int, int], ...]],
        'flowControl/MRR': Optional[int],
        'announceType': Optional[int],
    },
)


class StatusPayload(NamedTuple):
    version: int
    network_id: int
    head_td: int
    head_hash: Hash32
    head_number: BlockNumber
    genesis_hash: Hash32
    serve_headers: bool
    serve_chain_since: Optional[BlockNumber]
    serve_state_since: Optional[BlockNumber]
    serve_recent_state: Optional[bool]
    serve_recent_chain: Optional[bool]
    tx_relay: bool
    flow_control_bl: Optional[int]
    flow_control_mcr: Optional[Tuple[Tuple[int, int, int], ...]]
    flow_control_mrr: Optional[int]
    announce_type: Optional[int]

    @classmethod
    def from_pairs(cls, *pairs: Tuple[str, Any]) -> 'StatusPayload':
        pairs_dict = cast(_StatusPayloadDict, dict(pairs))

        return cls(
            version=pairs_dict['protocolVersion'],
            network_id=pairs_dict['networkId'],
            head_td=pairs_dict['headTd'],
            head_hash=pairs_dict['headHash'],
            head_number=pairs_dict['headNum'],
            genesis_hash=pairs_dict['genesisHash'],
            serve_headers=('serveHeaders' in pairs_dict),
            serve_chain_since=pairs_dict.get('serveChainSince'),
            serve_state_since=pairs_dict.get('serveStateSince'),
            serve_recent_chain=pairs_dict.get('serveRecentChain'),
            serve_recent_state=pairs_dict.get('serveRecentState'),
            tx_relay=('txRelay' in pairs_dict),
            flow_control_bl=pairs_dict.get('flowControl/BL'),
            flow_control_mcr=pairs_dict.get('flowControl/MRC'),
            flow_control_mrr=pairs_dict.get('flowControl/MRR'),
            announce_type=pairs_dict.get('announceType'),  # TODO: only in StatusV2
        )

    @to_tuple
    def to_pairs(self) -> Iterable[Tuple[str, Any]]:
        yield 'protocolVersion', self.version
        yield 'networkId', self.network_id
        yield 'headTd', self.head_td
        yield 'headHash', self.head_hash
        yield 'headNum', self.head_number
        yield 'genesisHash', self.genesis_hash
        if self.serve_headers is True:
            yield 'serveHeaders', None
        if self.serve_chain_since is not None:
            yield 'serveChainSince', self.serve_chain_since
        if self.serve_state_since is not None:
            yield 'serveStateSince', self.serve_state_since
        if self.serve_recent_chain is not None:
            yield 'serveRecentChain', self.serve_recent_chain
        if self.serve_recent_state is not None:
            yield 'serveRecentState', self.serve_recent_state
        if self.tx_relay is True:
            yield 'txRelay', None
        if self.flow_control_bl is not None:
            yield "flowControl/BL", self.flow_control_bl
        if self.flow_control_mcr is not None:
            yield "flowControl/MRC", self.flow_control_mcr
        if self.flow_control_mrr is not None:
            yield "flowControl/MRR", self.flow_control_mrr
        if self.announce_type is not None:
            yield "announceType", self.announce_type


class AnnouncePayload(NamedTuple):
    head_hash: Hash32
    head_number: BlockNumber
    head_td: int
    reorg_depth: int
    # TODO: params should be parsed into the same or similar structure as the StatusPayload
    params: Tuple[Tuple[str, bytes], ...]


class GetBlockHeadersPayload(NamedTuple):
    request_id: int
    query: BlockHeadersQuery


class BlockHeadersPayload(NamedTuple):
    request_id: int
    buffer_value: int
    headers: Tuple[BlockHeaderAPI, ...]


class GetBlockBodiesPayload(NamedTuple):
    request_id: int
    block_hashes: Tuple[Hash32, ...]


class BlockBodiesPayload(NamedTuple):
    request_id: int
    buffer_value: int
    bodies: Tuple[BlockBody, ...]


class GetReceiptsPayload(NamedTuple):
    request_id: int
    block_hashes: Tuple[Hash32, ...]


class ReceiptsPayload(NamedTuple):
    request_id: int
    buffer_value: int
    receipts: Tuple[Tuple[ReceiptAPI, ...], ...]


class ProofRequest(NamedTuple):
    block_hash: Hash32
    storage_key: Optional[Hash32]
    state_key: Hash32
    from_level: int


class GetProofsPayload(NamedTuple):
    request_id: int
    proofs: Tuple[ProofRequest, ...]


class ProofsPayloadV1(NamedTuple):
    request_id: int
    buffer_value: int
    proofs: Tuple[Tuple[bytes, ...], ...]


class ContractCodeRequest(NamedTuple):
    block_hash: Hash32
    account: Hash32


class GetContractCodesPayload(NamedTuple):
    request_id: int
    code_requests: Tuple[ContractCodeRequest, ...]


class ContractCodesPayload(NamedTuple):
    request_id: int
    buffer_value: int
    codes: Tuple[bytes, ...]


class ProofsPayloadV2(NamedTuple):
    request_id: int
    buffer_value: int
    proof: Tuple[bytes, ...]
