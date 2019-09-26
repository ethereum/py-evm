from typing import Tuple

from eth_typing import Hash32
from eth_utils.curried import (
    apply_formatter_at_index,
    apply_formatter_to_array,
)
from eth_utils.toolz import compose
from rlp import sedes

from eth.abc import BlockHeaderAPI, ReceiptAPI
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransactionFields

from p2p.commands import BaseCommand, RLPCodec

from trinity.protocol.common.payloads import BlockHeadersQuery
from trinity.rlp.block_body import BlockBody
from trinity.rlp.sedes import HashOrNumber, hash_sedes

from .payloads import (
    StatusPayload,
    NewBlockHash,
    BlockFields,
    NewBlockPayload,
)


STATUS_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.big_endian_int,
    hash_sedes,
    hash_sedes,
))


class Status(BaseCommand[StatusPayload]):
    protocol_command_id = 0
    serialization_codec = RLPCodec(
        sedes=STATUS_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: StatusPayload(*args),
        ),
    )


NEW_BLOCK_HASHES_STRUCTURE = sedes.CountableList(sedes.List([hash_sedes, sedes.big_endian_int]))


class NewBlockHashes(BaseCommand[Tuple[NewBlockHash, ...]]):
    protocol_command_id = 1
    serialization_codec = RLPCodec(
        sedes=NEW_BLOCK_HASHES_STRUCTURE,
        process_inbound_payload_fn=apply_formatter_to_array(lambda args: NewBlockHash(*args)),
    )


TRANSACTIONS_STRUCTURE = sedes.CountableList(BaseTransactionFields)


class Transactions(BaseCommand[Tuple[BaseTransactionFields, ...]]):
    protocol_command_id = 2
    serialization_codec: RLPCodec[Tuple[BaseTransactionFields, ...]] = RLPCodec(
        sedes=TRANSACTIONS_STRUCTURE,
    )


GET_BLOCK_HEADERS_STRUCTURE = sedes.List((
    HashOrNumber(),
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.boolean,
))


class GetBlockHeaders(BaseCommand[BlockHeadersQuery]):
    protocol_command_id = 3
    serialization_codec = RLPCodec(
        sedes=GET_BLOCK_HEADERS_STRUCTURE,
        process_inbound_payload_fn=lambda args: BlockHeadersQuery(*args),
    )


BLOCK_HEADERS_STRUCTURE = sedes.CountableList(BlockHeader)


class BlockHeaders(BaseCommand[Tuple[BlockHeaderAPI, ...]]):
    protocol_command_id = 4
    serialization_codec: RLPCodec[Tuple[BlockHeaderAPI, ...]] = RLPCodec(
        sedes=BLOCK_HEADERS_STRUCTURE,
    )


GET_BLOCK_BODIES_STRUCTURE = sedes.CountableList(hash_sedes)


class GetBlockBodies(BaseCommand[Tuple[Hash32, ...]]):
    protocol_command_id = 5
    serialization_codec: RLPCodec[Tuple[Hash32, ...]] = RLPCodec(
        sedes=GET_BLOCK_BODIES_STRUCTURE,
    )


BLOCK_BODIES_STRUCTURE = sedes.CountableList(BlockBody)


class BlockBodies(BaseCommand[Tuple[BlockBody, ...]]):
    protocol_command_id = 6
    serialization_codec: RLPCodec[Tuple[BlockBody, ...]] = RLPCodec(
        sedes=BLOCK_BODIES_STRUCTURE,
    )


NEW_BLOCK_STRUCTURE = sedes.List((
    sedes.List((
        BlockHeader,
        sedes.CountableList(BaseTransactionFields),
        sedes.CountableList(BlockHeader)
    )),
    sedes.big_endian_int
))


class NewBlock(BaseCommand[NewBlockPayload]):
    protocol_command_id = 7
    serialization_codec = RLPCodec(
        sedes=NEW_BLOCK_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: NewBlockPayload(*args),
            apply_formatter_at_index(
                lambda args: BlockFields(*args),
                0,
            )
        )
    )


GET_NODE_DATA_STRUCTURE = sedes.CountableList(hash_sedes)


class GetNodeData(BaseCommand[Tuple[Hash32, ...]]):
    protocol_command_id = 13
    serialization_codec: RLPCodec[Tuple[Hash32, ...]] = RLPCodec(
        sedes=GET_NODE_DATA_STRUCTURE,
    )


NODE_DATA_STRUCTURE = sedes.CountableList(sedes.binary)


class NodeData(BaseCommand[Tuple[bytes, ...]]):
    protocol_command_id = 14
    serialization_codec: RLPCodec[Tuple[bytes, ...]] = RLPCodec(
        sedes=NODE_DATA_STRUCTURE,
    )


GET_RECEIPTS_STRUCTURE = sedes.CountableList(hash_sedes)


class GetReceipts(BaseCommand[Tuple[Hash32, ...]]):
    protocol_command_id = 15
    serialization_codec: RLPCodec[Tuple[Hash32, ...]] = RLPCodec(
        sedes=GET_RECEIPTS_STRUCTURE,
    )


RECEIPTS_STRUCTURE = sedes.CountableList(sedes.CountableList(Receipt))


class Receipts(BaseCommand[Tuple[Tuple[ReceiptAPI, ...], ...]]):
    protocol_command_id = 16
    serialization_codec: RLPCodec[Tuple[Tuple[ReceiptAPI, ...], ...]] = RLPCodec(
        sedes=RECEIPTS_STRUCTURE,
    )
