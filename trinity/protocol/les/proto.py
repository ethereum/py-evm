from typing import (
    List,
    Tuple,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth.rlp.headers import BlockHeader

from p2p.protocol import (
    Protocol,
)

from trinity.protocol.common.peer import ChainInfo
from trinity._utils.les import gen_request_id

from .commands import (
    Status,
    StatusV2,
    Announce,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetBlockHeadersQuery,
    GetContractCodes,
    GetProofs,
    GetProofsV2,
    GetReceipts,
    BlockBodies,
    Receipts,
    Proofs,
    ProofsV2,
    ProofRequest,
    ContractCodeRequest,
    ContractCodes,
)
from . import constants

if TYPE_CHECKING:
    from .peer import LESPeer  # noqa: F401


class LESProtocol(Protocol):
    name = 'les'
    version = 1
    _commands = (
        Status,
        Announce,
        BlockHeaders, GetBlockHeaders,
        BlockBodies,
        Receipts,
        Proofs,
        ContractCodes,
    )
    cmd_length = 15
    peer: 'LESPeer'

    def send_handshake(self, chain_info: ChainInfo) -> None:
        resp = {
            'protocolVersion': self.version,
            'networkId': chain_info.network_id,
            'headTd': chain_info.total_difficulty,
            'headHash': chain_info.block_hash,
            'headNum': chain_info.block_number,
            'genesisHash': chain_info.genesis_hash,
            'serveHeaders': None,
            'serveChainSince': 0,
            # TODO: Uncomment once we start relaying transactions.
            # 'txRelay': None,
        }
        cmd = Status(self.cmd_id_offset, self.snappy_support)
        self.transport.send(*cmd.encode(resp))
        self.logger.debug("Sending LES/Status msg: %s", resp)

    def send_get_block_bodies(self, block_hashes: List[bytes], request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        if len(block_hashes) > constants.MAX_BODIES_FETCH:
            raise ValueError(
                f"Cannot ask for more than {constants.MAX_BODIES_FETCH} blocks in a single request"
            )
        data = {
            'request_id': request_id,
            'block_hashes': block_hashes,
        }
        header, body = GetBlockBodies(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id

    def send_get_block_headers(
            self,
            block_number_or_hash: Union[BlockNumber, Hash32],
            max_headers: int,
            skip: int,
            reverse: bool,
            request_id: int=None) -> int:
        """Send a GetBlockHeaders msg to the remote.

        This requests that the remote send us up to max_headers, starting from
        block_number_or_hash if reverse is False or ending at block_number_or_hash if reverse is
        True.
        """
        if request_id is None:
            request_id = gen_request_id()
        cmd = GetBlockHeaders(self.cmd_id_offset, self.snappy_support)
        data = {
            'request_id': request_id,
            'query': GetBlockHeadersQuery(
                block_number_or_hash,
                max_headers,
                skip,
                reverse,
            ),
        }
        header, body = cmd.encode(data)
        self.transport.send(header, body)

        return request_id

    def send_block_headers(
            self, headers: Tuple[BlockHeader, ...], buffer_value: int, request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        data = {
            'request_id': request_id,
            'headers': headers,
            'buffer_value': buffer_value,
        }
        header, body = BlockHeaders(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id

    def send_get_receipts(self, block_hash: bytes, request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        data = {
            'request_id': request_id,
            'block_hashes': [block_hash],
        }
        header, body = GetReceipts(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id

    def send_get_proof(self, block_hash: bytes, account_key: bytes, key: bytes, from_level: int,
                       request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        data = {
            'request_id': request_id,
            'proof_requests': [ProofRequest(block_hash, account_key, key, from_level)],
        }
        header, body = GetProofs(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id

    def send_get_contract_code(self, block_hash: bytes, key: bytes, request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        data = {
            'request_id': request_id,
            'code_requests': [ContractCodeRequest(block_hash, key)],
        }
        header, body = GetContractCodes(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id


class LESProtocolV2(LESProtocol):
    version = 2
    _commands = (  # type: ignore  # mypy doesn't like us overriding this.
        StatusV2,
        Announce,
        BlockHeaders, GetBlockHeaders,
        BlockBodies,
        Receipts,
        ProofsV2,
        ContractCodes,
    )
    cmd_length = 21

    def send_handshake(self, chain_info: ChainInfo) -> None:
        resp = {
            'announceType': constants.LES_ANNOUNCE_SIMPLE,
            'protocolVersion': self.version,
            'networkId': chain_info.network_id,
            'headTd': chain_info.total_difficulty,
            'headHash': chain_info.block_hash,
            'headNum': chain_info.block_number,
            'genesisHash': chain_info.genesis_hash,
            'serveHeaders': None,
            'serveChainSince': 0,
            'txRelay': None,
        }
        cmd = StatusV2(self.cmd_id_offset, self.snappy_support)
        self.logger.debug("Sending LES/Status msg: %s", resp)
        self.transport.send(*cmd.encode(resp))

    def send_get_proof(self,
                       block_hash: bytes,
                       account_key: bytes,
                       key: bytes,
                       from_level: int,
                       request_id: int=None) -> int:
        if request_id is None:
            request_id = gen_request_id()
        data = {
            'request_id': request_id,
            'proof_requests': [ProofRequest(block_hash, account_key, key, from_level)],
        }
        header, body = GetProofsV2(self.cmd_id_offset, self.snappy_support).encode(data)
        self.transport.send(header, body)

        return request_id
