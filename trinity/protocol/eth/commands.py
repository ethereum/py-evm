from typing import (
    Tuple,
)

from rlp import sedes

from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransactionFields

from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from trinity.protocol.common.commands import BaseBlockHeaders
from trinity.rlp.block_body import BlockBody
from trinity.rlp.sedes import HashOrNumber


hash_sedes = sedes.Binary(min_length=32, max_length=32)


class Status(Command):
    _cmd_id = 0
    structure = (
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('td', sedes.big_endian_int),
        ('best_hash', hash_sedes),
        ('genesis_hash', hash_sedes),
    )


class NewBlockHashes(Command):
    _cmd_id = 1
    structure = sedes.CountableList(sedes.List([hash_sedes, sedes.big_endian_int]))


class Transactions(Command):
    _cmd_id = 2
    structure = sedes.CountableList(BaseTransactionFields)


class GetBlockHeaders(Command):
    _cmd_id = 3
    structure = (
        ('block_number_or_hash', HashOrNumber()),
        ('max_headers', sedes.big_endian_int),
        ('skip', sedes.big_endian_int),
        ('reverse', sedes.boolean),
    )


class BlockHeaders(BaseBlockHeaders):
    _cmd_id = 4
    structure = sedes.CountableList(BlockHeader)

    def extract_headers(self, msg: _DecodedMsgType) -> Tuple[BlockHeader, ...]:
        return tuple(msg)


class GetBlockBodies(Command):
    _cmd_id = 5
    structure = sedes.CountableList(sedes.binary)


class BlockBodies(Command):
    _cmd_id = 6
    structure = sedes.CountableList(BlockBody)


class NewBlock(Command):
    _cmd_id = 7
    structure = (
        ('block', sedes.List([BlockHeader,
                              sedes.CountableList(BaseTransactionFields),
                              sedes.CountableList(BlockHeader)])),
        ('total_difficulty', sedes.big_endian_int),
    )


class GetNodeData(Command):
    _cmd_id = 13
    structure = sedes.CountableList(hash_sedes)


class NodeData(Command):
    _cmd_id = 14
    structure = sedes.CountableList(sedes.binary)


class GetReceipts(Command):
    _cmd_id = 15
    structure = sedes.CountableList(hash_sedes)


class Receipts(Command):
    _cmd_id = 16
    structure = sedes.CountableList(sedes.CountableList(Receipt))
