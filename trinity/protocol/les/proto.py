from typing import (
    List,
    Tuple,
    TYPE_CHECKING,
)

from eth.rlp.headers import BlockHeader

from p2p.protocol import (
    Protocol,
)

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
from .requests import HeaderRequest

if TYPE_CHECKING:
    from p2p.peer import (  # noqa: F401
        ChainInfo
    )


class LESProtocol(Protocol):
    name = 'les'
    version = 1
    _commands = [Status, Announce, BlockHeaders, GetBlockHeaders, BlockBodies, Receipts, Proofs,
                 ContractCodes]
    cmd_length = 15

    def send_handshake(self, chain_info: 'ChainInfo') -> None:
        resp = {
            'protocolVersion': self.version,
            'networkId': self.peer.network_id,
            'headTd': chain_info.total_difficulty,
            'headHash': chain_info.block_hash,
            'headNum': chain_info.block_number,
            'genesisHash': chain_info.genesis_hash,
            'serveHeaders': None,
            'serveChainSince': 0,
            'txRelay': None,
        }
        cmd = Status(self.cmd_id_offset)
        self.send(*cmd.encode(resp))
        self.logger.debug("Sending LES/Status msg: %s", resp)

    def send_get_block_bodies(self, block_hashes: List[bytes], request_id: int) -> None:
        if len(block_hashes) > constants.MAX_BODIES_FETCH:
            raise ValueError(
                "Cannot ask for more than {} blocks in a single request".format(
                    constants.MAX_BODIES_FETCH))
        data = {
            'request_id': request_id,
            'block_hashes': block_hashes,
        }
        header, body = GetBlockBodies(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_get_block_headers(self, request: HeaderRequest) -> None:
        """Send a GetBlockHeaders msg to the remote.

        This requests that the remote send us up to max_headers, starting from
        block_number_or_hash if reverse is False or ending at block_number_or_hash if reverse is
        True.
        """
        if request.max_headers > constants.MAX_HEADERS_FETCH:
            raise ValueError(
                "Cannot ask for more than {} block headers in a single request".format(
                    constants.MAX_HEADERS_FETCH))
        cmd = GetBlockHeaders(self.cmd_id_offset)
        # Number of block headers to skip between each item (i.e. step in python APIs).
        data = {
            'request_id': request.request_id,
            'query': GetBlockHeadersQuery(
                request.block_number_or_hash,
                request.max_headers,
                request.skip,
                request.reverse,
            ),
        }
        header, body = cmd.encode(data)
        self.send(header, body)

    def send_block_headers(
            self, headers: Tuple[BlockHeader, ...], buffer_value: int, request_id: int) -> None:
        data = {
            'request_id': request_id,
            'headers': headers,
            'buffer_value': buffer_value,
        }
        header, body = BlockHeaders(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_get_receipts(self, block_hash: bytes, request_id: int) -> None:
        data = {
            'request_id': request_id,
            'block_hashes': [block_hash],
        }
        header, body = GetReceipts(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_get_proof(self, block_hash: bytes, account_key: bytes, key: bytes, from_level: int,
                       request_id: int) -> None:
        data = {
            'request_id': request_id,
            'proof_requests': [ProofRequest(block_hash, account_key, key, from_level)],
        }
        header, body = GetProofs(self.cmd_id_offset).encode(data)
        self.send(header, body)

    def send_get_contract_code(self, block_hash: bytes, key: bytes, request_id: int) -> None:
        data = {
            'request_id': request_id,
            'code_requests': [ContractCodeRequest(block_hash, key)],
        }
        header, body = GetContractCodes(self.cmd_id_offset).encode(data)
        self.send(header, body)


class LESProtocolV2(LESProtocol):
    version = 2
    _commands = [StatusV2, Announce, BlockHeaders, GetBlockHeaders, BlockBodies, Receipts,
                 ProofsV2, ContractCodes]
    cmd_length = 21

    def send_handshake(self, chain_info: 'ChainInfo') -> None:
        resp = {
            'announceType': constants.LES_ANNOUNCE_SIMPLE,
            'protocolVersion': self.version,
            'networkId': self.peer.network_id,
            'headTd': chain_info.total_difficulty,
            'headHash': chain_info.block_hash,
            'headNum': chain_info.block_number,
            'genesisHash': chain_info.genesis_hash,
            'serveHeaders': None,
            'serveChainSince': 0,
            'txRelay': None,
        }
        cmd = StatusV2(self.cmd_id_offset)
        self.logger.debug("Sending LES/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def send_get_proof(self,
                       block_hash: bytes,
                       account_key: bytes,
                       key: bytes,
                       from_level: int,
                       request_id: int) -> None:
        data = {
            'request_id': request_id,
            'proof_requests': [ProofRequest(block_hash, account_key, key, from_level)],
        }
        header, body = GetProofsV2(self.cmd_id_offset).encode(data)
        self.send(header, body)
