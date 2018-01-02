import logging
from typing import Any, cast, Dict, List, Union

import rlp
from rlp import sedes

from eth_utils import encode_hex

from .constants import MAX_HEADERS_FETCH
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt
from evm.rlp.transactions import BaseTransaction
from evm.p2p.exceptions import HandshakeFailure
from evm.p2p.p2p_proto import DisconnectReason
from evm.p2p.protocol import (
    Command,
    Protocol,
    _DecodedMsgType,
)
from evm.p2p.sedes import HashOrNumber


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

    def handle(self, proto: 'Protocol', data: bytes):
        proto = cast(ETHProtocol, proto)
        decoded = super().handle(proto, data)
        # TODO: Actually send the requested block headers. For now we reply with an empty list
        # just so nodes don't disconnect us straight away
        proto.send_block_headers([])
        return decoded


class BlockHeaders(Command):
    _cmd_id = 4
    structure = sedes.CountableList(BlockHeader)


class GetBlockBodies(Command):
    _cmd_id = 5
    structure = sedes.CountableList(sedes.binary)

    def handle(self, proto: 'Protocol', data: bytes):
        proto = cast(ETHProtocol, proto)
        decoded = super().handle(proto, data)
        # TODO: Actually send the requested block bodies. For now we reply with an empty list
        # just so nodes don't disconnect us straight away
        proto.send_block_bodies([])
        return decoded


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


# TODO: Implement handling of incoming GetNodeData msgs.
class GetNodeData(Command):
    _cmd_id = 13
    structure = sedes.CountableList(sedes.binary)


class NodeData(Command):
    _cmd_id = 14
    structure = sedes.CountableList(sedes.binary)


# TODO: Implement handling of incoming GetReceipts msgs.
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
    handshake_msg_type = Status
    cmd_length = 17
    logger = logging.getLogger("evm.p2p.eth.ETHProtocol")

    def send_handshake(self, head_info):
        resp = {
            'protocol_version': self.version,
            'network_id': self.peer.network_id,
            'td': head_info.total_difficulty,
            'best_hash': head_info.block_hash,
            'genesis_hash': head_info.genesis_hash,
        }
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending ETH/Status msg: %s", resp)
        self.send(*cmd.encode(resp))

    def process_handshake(self, decoded_msg: _DecodedMsgType) -> None:
        decoded_msg = cast(Dict[str, Any], decoded_msg)
        if decoded_msg['network_id'] != self.peer.network_id:
            self.logger.debug(
                "%s network (%s) does not match ours (%s), disconnecting",
                self.peer, decoded_msg['network_id'], self.peer.network_id)
            raise HandshakeFailure(DisconnectReason.other)
        if decoded_msg['genesis_hash'] != self.peer.genesis.hash:
            self.logger.debug(
                "%s genesis (%s) does not match ours (%s), disconnecting",
                self.peer, encode_hex(decoded_msg['genesis_hash']), self.peer.genesis.hex_hash)
            raise HandshakeFailure(DisconnectReason.other)

    def send_get_node_data(self, node_hashes: List[bytes]) -> None:
        cmd = GetNodeData(self.cmd_id_offset)
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
        cmd = GetBlockHeaders(self.cmd_id_offset)
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
        cmd = BlockHeaders(self.cmd_id_offset)
        header, body = cmd.encode([rlp.encode(header) for header in headers])
        self.send(header, body)

    def send_get_block_bodies(self, block_hashes: bytes) -> None:
        cmd = GetBlockBodies(self.cmd_id_offset)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)

    def send_block_bodies(self, blocks: List[BlockBody]) -> None:
        cmd = BlockBodies(self.cmd_id_offset)
        header, body = cmd.encode([rlp.encode(block) for block in blocks])
        self.send(header, body)

    def send_get_receipts(self, block_hashes: bytes) -> None:
        cmd = GetReceipts(self.cmd_id_offset)
        header, body = cmd.encode(block_hashes)
        self.send(header, body)
