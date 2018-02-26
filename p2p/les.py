from typing import Any, cast, Dict, Generator, List, Tuple, Union

import rlp
from rlp import sedes

from eth_utils import (
    encode_hex,
    to_dict,
)

from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.rlp.transactions import BaseTransaction

from p2p.protocol import (
    Command,
    Protocol,
    _DecodedMsgType,
)
from p2p.sedes import HashOrNumber

from .constants import LES_ANNOUNCE_SIMPLE


# Max number of items we can ask for in LES requests. These are the values used in geth and if we
# ask for more than this the peers will disconnect from us.
MAX_HEADERS_FETCH = 192
MAX_BODIES_FETCH = 32
MAX_RECEIPTS_FETCH = 128
MAX_CODE_FETCH = 64
MAX_PROOFS_FETCH = 64
MAX_HEADER_PROOFS_FETCH = 64


class HeadInfo:
    def __init__(self, block_number, block_hash, total_difficulty, reorg_depth):
        self.block_number = block_number
        self.block_hash = block_hash
        self.total_difficulty = total_difficulty
        self.reorg_depth = reorg_depth

    def __str__(self):
        return "HeadInfo{{block:{}, hash:{}, td:{}, reorg_depth:{}}}".format(
            self.block_number, encode_hex(self.block_hash), self.total_difficulty,
            self.reorg_depth)


class Status(Command):
    _cmd_id = 0
    decode_strict = False
    # A list of (key, value) pairs is all a Status msg contains, but since the values can be of
    # any type, we need to use the raw sedes here and do the actual deserialization in
    # decode_payload().
    structure = sedes.CountableList(sedes.List([sedes.binary, sedes.raw]))
    # The sedes used for each key in the list above.
    items_sedes = {
        'protocolVersion': sedes.big_endian_int,
        'networkId': sedes.big_endian_int,
        'headTd': sedes.big_endian_int,
        'headHash': sedes.binary,
        'headNum': sedes.big_endian_int,
        'genesisHash': sedes.binary,
        'serveHeaders': None,
        'serveChainSince': sedes.big_endian_int,
        'serveStateSince': sedes.big_endian_int,
        'txRelay': None,
        'flowControl/BL': sedes.big_endian_int,
        'flowControl/MRC': sedes.CountableList(
            sedes.List([sedes.big_endian_int, sedes.big_endian_int, sedes.big_endian_int])),
        'flowControl/MRR': sedes.big_endian_int,
    }

    @to_dict
    def decode_payload(self, rlp_data: bytes) -> Generator[Tuple[str, Any], None, None]:
        data = cast(List[Tuple[bytes, bytes]], super(Status, self).decode_payload(rlp_data))
        # The LES/Status msg contains an arbitrary list of (key, value) pairs, where values can
        # have different types and unknown keys should be ignored for forward compatibility
        # reasons, so here we need an extra pass to deserialize each of the key/value pairs we
        # know about.
        for key, value in data:
            # The sedes.binary we use in .structure above will give us a bytes value here, but
            # using bytes as dictionary keys makes it impossible to use the dict() constructor
            # with keyword arguments, so we convert them to strings here.
            str_key = key.decode('ascii')
            if str_key not in self.items_sedes:
                continue
            item_sedes = self.items_sedes[str_key]
            if item_sedes is not None:
                yield str_key, item_sedes.deserialize(value)
            else:
                yield str_key, value

    def encode_payload(self, data):
        response = [
            (key, self.items_sedes[key].serialize(value))
            for key, value
            in sorted(data.items())
        ]
        return super(Status, self).encode_payload(response)

    def as_head_info(self, decoded: _DecodedMsgType) -> HeadInfo:
        decoded = cast(Dict[str, Any], decoded)
        return HeadInfo(
            block_number=decoded['headNum'],
            block_hash=decoded['headHash'],
            total_difficulty=decoded['headTd'],
            reorg_depth=0,
        )


class Announce(Command):
    _cmd_id = 1
    structure = [
        ('head_hash', sedes.binary),
        ('head_number', sedes.big_endian_int),
        ('head_td', sedes.big_endian_int),
        ('reorg_depth', sedes.big_endian_int),
        ('params', sedes.CountableList(sedes.List([sedes.binary, sedes.raw]))),
    ]
    # TODO: The params CountableList above may contain any of the values from the Status msg.
    # Need to extend this command to process that too.

    def as_head_info(self, decoded: _DecodedMsgType) -> HeadInfo:
        decoded = cast(Dict[str, Any], decoded)
        return HeadInfo(
            block_number=decoded['head_number'],
            block_hash=decoded['head_hash'],
            total_difficulty=decoded['head_td'],
            reorg_depth=decoded['reorg_depth'],
        )


class GetBlockHeadersQuery(rlp.Serializable):
    fields = [
        ('block_number_or_hash', HashOrNumber()),
        ('max_headers', sedes.big_endian_int),
        ('skip', sedes.big_endian_int),
        ('reverse', sedes.big_endian_int),
    ]


class GetBlockHeaders(Command):
    _cmd_id = 2
    structure = [
        ('request_id', sedes.big_endian_int),
        ('query', GetBlockHeadersQuery),
    ]


class BlockHeaders(Command):
    _cmd_id = 3
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('headers', sedes.CountableList(BlockHeader)),
    ]


class GetBlockBodies(Command):
    _cmd_id = 4
    structure = [
        ('request_id', sedes.big_endian_int),
        ('block_hashes', sedes.CountableList(sedes.binary)),
    ]


class LESBlockBody(rlp.Serializable):
    fields = [
        ('transactions', rlp.sedes.CountableList(BaseTransaction)),
        ('uncles', rlp.sedes.CountableList(BlockHeader))
    ]


class BlockBodies(Command):
    _cmd_id = 5
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('bodies', sedes.CountableList(LESBlockBody)),
    ]


class GetReceipts(Command):
    _cmd_id = 6
    structure = [
        ('request_id', sedes.big_endian_int),
        ('block_hashes', sedes.CountableList(sedes.binary)),
    ]


class Receipts(Command):
    _cmd_id = 7
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('receipts', sedes.CountableList(sedes.CountableList(Receipt))),
    ]


class ProofRequest(rlp.Serializable):
    fields = [
        ('block_hash', sedes.binary),
        ('account_key', sedes.binary),
        ('key', sedes.binary),
        ('from_level', sedes.big_endian_int),
    ]


class GetProofs(Command):
    _cmd_id = 8
    structure = [
        ('request_id', sedes.big_endian_int),
        ('proof_requests', sedes.CountableList(ProofRequest)),
    ]


class Proofs(Command):
    _cmd_id = 9
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('proofs', sedes.CountableList(sedes.CountableList(sedes.raw))),
    ]

    def decode_payload(self, rlp_data: bytes) -> _DecodedMsgType:
        decoded = super().decode_payload(rlp_data)
        decoded = cast(Dict[str, Any], decoded)
        # This is just to make Proofs messages compatible with ProofsV2, so that LightChain
        # doesn't have to special-case them. Soon we should be able to drop support for LES/1
        # anyway, and then all this code will go away.
        if not decoded['proofs']:
            decoded['proof'] = []
        else:
            decoded['proof'] = decoded['proofs'][0]
        return decoded


class ContractCodeRequest(rlp.Serializable):
    fields = [
        ('block_hash', sedes.binary),
        ('key', sedes.binary),
    ]


class GetContractCodes(Command):
    _cmd_id = 10
    structure = [
        ('request_id', sedes.big_endian_int),
        ('code_requests', sedes.CountableList(ContractCodeRequest)),
    ]


class ContractCodes(Command):
    _cmd_id = 11
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('codes', sedes.CountableList(sedes.binary)),
    ]


class LESProtocol(Protocol):
    name = b'les'
    version = 1
    _commands = [Status, Announce, BlockHeaders, BlockBodies, Receipts, Proofs, ContractCodes]
    cmd_length = 15

    def send_handshake(self, head_info):
        resp = {
            'protocolVersion': self.version,
            'networkId': self.peer.network_id,
            'headTd': head_info.total_difficulty,
            'headHash': head_info.block_hash,
            'headNum': head_info.block_number,
            'genesisHash': head_info.genesis_hash,
        }
        cmd = Status(self)
        self.send(*cmd.encode(resp))
        self.logger.debug("Sending LES/Status msg: %s", resp)

    def send_get_block_bodies(self, block_hashes: List[bytes], request_id: int) -> None:
        if len(block_hashes) > MAX_BODIES_FETCH:
            raise ValueError(
                "Cannot ask for more than {} blocks in a single request".format(
                    MAX_BODIES_FETCH))
        data = {
            'request_id': request_id,
            'block_hashes': block_hashes,
        }
        header, body = GetBlockBodies(self).encode(data)
        self.send(header, body)

    def send_get_block_headers(self, block_number_or_hash: Union[int, bytes],
                               max_headers: int, request_id: int, reverse: bool = True
                               ) -> None:
        """Send a GetBlockHeaders msg to the remote.

        This requests that the remote send us up to max_headers, starting from
        block_number_or_hash if reverse is False or ending at block_number_or_hash if reverse is
        True.
        """
        if max_headers > MAX_HEADERS_FETCH:
            raise ValueError(
                "Cannot ask for more than {} block headers in a single request".format(
                    MAX_HEADERS_FETCH))
        cmd = GetBlockHeaders(self)
        # Number of block headers to skip between each item (i.e. step in python APIs).
        skip = 0
        data = {
            'request_id': request_id,
            'query': GetBlockHeadersQuery(block_number_or_hash, max_headers, skip, reverse),
        }
        header, body = cmd.encode(data)
        self.send(header, body)

    def send_get_receipts(self, block_hash: bytes, request_id: int) -> None:
        data = {
            'request_id': request_id,
            'block_hashes': [block_hash],
        }
        header, body = GetReceipts(self).encode(data)
        self.send(header, body)

    def send_get_proof(self, block_hash: bytes, account_key: bytes, key: bytes, from_level: int,
                       request_id: int) -> None:
        data = {
            'request_id': request_id,
            'proof_requests': [ProofRequest(block_hash, account_key, key, from_level)],
        }
        header, body = GetProofs(self).encode(data)
        self.send(header, body)

    def send_get_contract_code(self, block_hash: bytes, key: bytes, request_id: int) -> None:
        data = {
            'request_id': request_id,
            'code_requests': [ContractCodeRequest(block_hash, key)],
        }
        header, body = GetContractCodes(self).encode(data)
        self.send(header, body)


class StatusV2(Status):
    _cmd_id = 0

    def __init__(self, proto: 'Protocol') -> None:
        super().__init__(proto)
        self.items_sedes['announceType'] = sedes.big_endian_int


class GetProofsV2(GetProofs):
    _cmd_id = 15


class ProofsV2(Command):
    _cmd_id = 16
    structure = [
        ('request_id', sedes.big_endian_int),
        ('buffer_value', sedes.big_endian_int),
        ('proof', sedes.CountableList(sedes.raw)),
    ]


class LESProtocolV2(LESProtocol):
    version = 2
    _commands = [StatusV2, Announce, BlockHeaders, BlockBodies, Receipts, ProofsV2, ContractCodes]
    cmd_length = 21

    def send_handshake(self, head_info):
        resp = {
            'announceType': LES_ANNOUNCE_SIMPLE,
            'protocolVersion': self.version,
            'networkId': self.peer.network_id,
            'headTd': head_info.total_difficulty,
            'headHash': head_info.block_hash,
            'headNum': head_info.block_number,
            'genesisHash': head_info.genesis_hash,
        }
        cmd = StatusV2(self)
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
        header, body = GetProofsV2(self).encode(data)
        self.send(header, body)
