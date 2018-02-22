import logging
from typing import List, Union

import rlp
from rlp import sedes

from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.rlp.transactions import BaseTransaction

from p2p.protocol import (
    Command,
    Protocol,
)
from p2p.sedes import HashOrNumber


# Max number of items we can ask for in ETH requests. These are the values used in geth and if we
# ask for more than this the peers will disconnect from us.
MAX_STATE_FETCH = 384
MAX_BODIES_FETCH = 128
MAX_RECEIPTS_FETCH = 256
MAX_HEADERS_FETCH = 192


class Status(Command):
    _cmd_id = 0
    structure = [
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('td', sedes.big_endian_int),
        ('best_hash', sedes.binary),
        ('genesis_hash', sedes.binary),
    ]


class NewBlockHashes(Command):
    _cmd_id = 1
    structure = sedes.CountableList(sedes.List([sedes.binary, sedes.big_endian_int]))


class Transactions(Command):
    _cmd_id = 2
    structure = sedes.CountableList(BaseTransaction)


class GetBlockHeaders(Command):
    _cmd_id = 3
    structure = [
        ('block_number_or_hash', HashOrNumber()),
        ('max_headers', sedes.big_endian_int),
        ('skip', sedes.big_endian_int),
        ('reverse', sedes.big_endian_int),
    ]


class BlockHeaders(Command):
    _cmd_id = 4
    structure = sedes.CountableList(BlockHeader)


class GetBlockBodies(Command):
    _cmd_id = 5
    structure = sedes.CountableList(sedes.binary)


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(BaseTransaction)),
        ('uncles', sedes.CountableList(BlockHeader))
    ]


class BlockBodies(Command):
    _cmd_id = 6
    structure = sedes.CountableList(BlockBody)


class NewBlock(Command):
    _cmd_id = 7
    structure = [
        ('block', sedes.List([BlockHeader,
                              sedes.CountableList(BaseTransaction),
                              sedes.CountableList(BlockHeader)])),
        ('total_difficulty', sedes.big_endian_int)]


class GetNodeData(Command):
    _cmd_id = 13
    structure = sedes.CountableList(sedes.binary)


class NodeData(Command):
    _cmd_id = 14
    structure = sedes.CountableList(sedes.binary)


class GetReceipts(Command):
    _cmd_id = 15
    structure = sedes.CountableList(sedes.binary)


class Receipts(Command):
    _cmd_id = 16
    structure = sedes.CountableList(sedes.CountableList(Receipt))


class ETHProtocol(Protocol):
    name = b'eth'
    version = 63
    _commands = [
        Status, NewBlockHashes, Transactions, GetBlockHeaders, BlockHeaders, BlockHeaders,
        GetBlockBodies, BlockBodies, NewBlock, GetNodeData, NodeData,
        GetReceipts, Receipts]
    cmd_length = 17
    logger = logging.getLogger("p2p.eth.ETHProtocol")

    def send_handshake(self, head_info):
        resp = {
            'protocol_version': self.version,
            'network_id': self.peer.network_id,
            'td': head_info.total_difficulty,
            'best_hash': head_info.block_hash,
            'genesis_hash': head_info.genesis_hash,
        }
        cmd = Status(self)
        self.logger.debug("Sending ETH/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def send_get_node_data(self, node_hashes: List[bytes]) -> None:
        cmd = GetNodeData(self)
        header, body = cmd.encode(node_hashes)
        self.send(header, body)

    def send_get_block_headers(self, block_number_or_hash: Union[int, bytes],
                               max_headers: int, reverse: bool = True
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
            'block_number_or_hash': block_number_or_hash,
            'max_headers': max_headers,
            'skip': skip,
            'reverse': reverse}
        header, body = cmd.encode(data)
        self.send(header, body)

    def send_block_headers(self, headers: List[BlockHeader]) -> None:
        cmd = BlockHeaders(self)
        header, body = cmd.encode([rlp.encode(header) for header in headers])
        self.send(header, body)

    def send_get_block_bodies(self, block_hashes: List[bytes]) -> None:
        cmd = GetBlockBodies(self)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)

    def send_block_bodies(self, blocks: List[BlockBody]) -> None:
        cmd = BlockBodies(self)
        header, body = cmd.encode([rlp.encode(block) for block in blocks])
        self.send(header, body)

    def send_get_receipts(self, block_hashes: List[bytes]) -> None:
        cmd = GetReceipts(self)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)
