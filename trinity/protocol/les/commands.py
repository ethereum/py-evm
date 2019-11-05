from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    Tuple,
    Union,
)

from eth_typing import Hash32
from eth_utils import (
    to_tuple,
    ValidationError,
)
from eth_utils.curried import (
    apply_formatter_at_index,
    apply_formatter_to_array,
)
from eth_utils.toolz import compose

import rlp
from rlp import sedes

from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt

from p2p.abc import SerializationCodecAPI
from p2p.commands import BaseCommand, RLPCodec

from trinity.rlp.block_body import BlockBody
from trinity.rlp.sedes import HashOrNumber, hash_sedes

from .payloads import (
    AnnouncePayload,
    BlockBodiesPayload,
    BlockHeadersPayload,
    BlockHeadersQuery,
    ContractCodeRequest,
    ContractCodesPayload,
    GetBlockBodiesPayload,
    GetBlockHeadersPayload,
    GetContractCodesPayload,
    GetProofsPayload,
    GetReceiptsPayload,
    ProofRequest,
    ProofsPayloadV1,
    ProofsPayloadV2,
    ReceiptsPayload,
    StatusPayload,
)


#
# 0: Status
#
STATUS_V1_ITEM_SEDES = {
    'protocolVersion': sedes.big_endian_int,
    'networkId': sedes.big_endian_int,
    'headTd': sedes.big_endian_int,
    'headHash': hash_sedes,
    'headNum': sedes.big_endian_int,
    'genesisHash': hash_sedes,
    'serveHeaders': None,
    'serveChainSince': sedes.big_endian_int,
    'serveRecentChain': sedes.big_endian_int,
    'serveStateSince': sedes.big_endian_int,
    'serveRecentState': sedes.big_endian_int,
    'txRelay': None,
    'flowControl/BL': sedes.big_endian_int,
    'flowControl/MRC': sedes.CountableList(
        sedes.List([sedes.big_endian_int, sedes.big_endian_int, sedes.big_endian_int])),
    'flowControl/MRR': sedes.big_endian_int,
}


STATUS_STRUCTURE = sedes.CountableList(sedes.List([sedes.text, sedes.raw]))


class StatusSerializationCodec(SerializationCodecAPI[StatusPayload]):
    item_sedes: ClassVar[Dict[str, Any]]

    @to_tuple
    def _encode_items(self, *items: Tuple[str, Any]) -> Iterable[Tuple[str, bytes]]:
        for key, value in items:
            if key not in self.item_sedes:
                raise ValidationError(f"Unknown key: {key}")
            item_sedes = self.item_sedes[key]
            if item_sedes is None:
                yield (key, b'')
            else:
                yield (key, item_sedes.serialize(value))

    def encode(self, payload: StatusPayload) -> bytes:
        items = self._encode_items(*payload.to_pairs())
        return rlp.encode(items, sedes=STATUS_STRUCTURE)

    @to_tuple
    def _decode_items(self, *items: Tuple[str, bytes]) -> Iterable[Tuple[str, Any]]:
        for key, raw_value in items:
            if key not in self.item_sedes:
                yield key, raw_value
                # TODO: maybe log this?
                continue

            item_sedes = self.item_sedes[key]
            if item_sedes is None:
                yield (key, None)
            else:
                value = item_sedes.deserialize(raw_value)
                yield (key, value)

    def decode(self, data: bytes) -> StatusPayload:
        raw_items = rlp.decode(data, sedes=STATUS_STRUCTURE, recursive_cache=True)
        items = self._decode_items(*raw_items)
        return StatusPayload.from_pairs(*items)


class StatusSerializationCodecV1(StatusSerializationCodec):
    item_sedes = STATUS_V1_ITEM_SEDES


class StatusV1(BaseCommand[StatusPayload]):
    protocol_command_id = 0
    serialization_codec = StatusSerializationCodecV1()


#
# 1: Announce
#
ANNOUNCE_STRUCTURE = sedes.List((
    hash_sedes,  # head_hash
    sedes.big_endian_int,  # head_number
    sedes.big_endian_int,  # head_td
    sedes.big_endian_int,  # reorg_depth
    # TODO: The params CountableList may contain any of the values from the
    # Status msg.  Need to extend this command to process that too.
    sedes.CountableList(sedes.List((sedes.text, sedes.raw))),  # params
))


class Announce(BaseCommand[AnnouncePayload]):
    protocol_command_id = 1
    serialization_codec = RLPCodec(
        sedes=ANNOUNCE_STRUCTURE,
        process_inbound_payload_fn=lambda args: AnnouncePayload(*args),
    )


GET_BLOCK_HEADERS_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.List((HashOrNumber(), sedes.big_endian_int, sedes.big_endian_int, sedes.boolean)),
))


class GetBlockHeaders(BaseCommand[GetBlockHeadersPayload]):
    protocol_command_id = 2
    serialization_codec = RLPCodec(
        sedes=GET_BLOCK_HEADERS_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: GetBlockHeadersPayload(*args),
            apply_formatter_at_index(lambda args: BlockHeadersQuery(*args), 1)
        ),
    )


BLOCK_HEADERS_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(BlockHeader),
))


class BlockHeaders(BaseCommand[BlockHeadersPayload]):
    protocol_command_id = 3
    serialization_codec = RLPCodec(
        sedes=BLOCK_HEADERS_STRUCTURE,
        process_inbound_payload_fn=lambda args: BlockHeadersPayload(*args),
    )


GET_BLOCK_BODIES_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.CountableList(hash_sedes),
))


class GetBlockBodies(BaseCommand[GetBlockBodiesPayload]):
    protocol_command_id = 4
    serialization_codec = RLPCodec(
        sedes=GET_BLOCK_BODIES_STRUCTURE,
        process_inbound_payload_fn=lambda args: GetBlockBodiesPayload(*args),
    )


BLOCK_BODIES_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(BlockBody),
))


class BlockBodies(BaseCommand[BlockBodiesPayload]):
    protocol_command_id = 5
    serialization_codec = RLPCodec(
        sedes=BLOCK_BODIES_STRUCTURE,
        process_inbound_payload_fn=lambda args: BlockBodiesPayload(*args),
    )


GET_RECEIPTS_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.CountableList(sedes.binary),
))


class GetReceipts(BaseCommand[GetReceiptsPayload]):
    protocol_command_id = 6
    serialization_codec = RLPCodec(
        sedes=GET_RECEIPTS_STRUCTURE,
        process_inbound_payload_fn=lambda args: GetReceiptsPayload(*args),
    )


RECEIPTS_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(sedes.CountableList(Receipt)),
))


class Receipts(BaseCommand[ReceiptsPayload]):
    protocol_command_id = 7
    serialization_codec = RLPCodec(
        sedes=RECEIPTS_STRUCTURE,
        process_inbound_payload_fn=lambda args: ReceiptsPayload(*args),
    )


GET_PROOFS_V1_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.CountableList(sedes.List((
        sedes.binary,
        sedes.binary,
        sedes.binary,
        sedes.big_endian_int,
    ))),
))


GetProofsV1Raw = Tuple[int, Tuple[Tuple[Hash32, Union[bytes, Hash32], Hash32, int], ...]]


def normalize_get_proofs_payload(payload: GetProofsPayload) -> GetProofsV1Raw:
    proof_requests = tuple(
        (
            block_hash,
            b'' if storage_key is None else storage_key,
            state_key,
            from_level,
        ) for (block_hash, storage_key, state_key, from_level) in payload.proofs
    )
    return (payload.request_id, proof_requests)


def denormalize_get_proofs_payload(raw_payload: GetProofsV1Raw) -> GetProofsPayload:
    request_id, raw_proof_requests = raw_payload
    proof_requests = tuple(
        ProofRequest(
            block_hash,
            Hash32(None if storage_key == b'' else storage_key),
            state_key,
            from_level,
        ) for (block_hash, storage_key, state_key, from_level) in raw_proof_requests
    )
    return GetProofsPayload(request_id, proof_requests)


class GetProofsV1(BaseCommand[GetProofsPayload]):
    protocol_command_id = 8
    serialization_codec = RLPCodec(
        sedes=GET_PROOFS_V1_STRUCTURE,
        process_outbound_payload_fn=normalize_get_proofs_payload,
        process_inbound_payload_fn=denormalize_get_proofs_payload,
    )


PROOFS_V1_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(sedes.CountableList(sedes.raw)),
))


class ProofsV1(BaseCommand[ProofsPayloadV1]):
    protocol_command_id = 9
    serialization_codec = RLPCodec(
        sedes=PROOFS_V1_STRUCTURE,
        process_inbound_payload_fn=lambda args: ProofsPayloadV1(*args),
    )


GET_CONTRACT_CODES_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.CountableList(sedes.List((
        sedes.binary,
        sedes.binary,
    )))
))


class GetContractCodes(BaseCommand[GetContractCodesPayload]):
    protocol_command_id = 10
    serialization_codec = RLPCodec(
        sedes=GET_CONTRACT_CODES_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: GetContractCodesPayload(*args),
            apply_formatter_at_index(
                apply_formatter_to_array(lambda args: ContractCodeRequest(*args)),
                1,
            ),
        ),
    )


CONTRACT_CODES_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(sedes.binary),
))


class ContractCodes(BaseCommand[ContractCodesPayload]):
    protocol_command_id = 11
    serialization_codec = RLPCodec(
        sedes=CONTRACT_CODES_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: ContractCodesPayload(*args),
        ),
    )


STATUS_V2_ITEM_SEDES = {
    'protocolVersion': sedes.big_endian_int,
    'networkId': sedes.big_endian_int,
    'headTd': sedes.big_endian_int,
    'headHash': sedes.binary,
    'headNum': sedes.big_endian_int,
    'genesisHash': sedes.binary,
    'serveHeaders': None,
    'serveChainSince': sedes.big_endian_int,
    # 'serveRecentChain': sedes.big_endian_int,  # not added till v3
    'serveStateSince': sedes.big_endian_int,
    # 'serveRecentState': sedes.big_endian_int,  # not added till v3
    'txRelay': None,
    'flowControl/BL': sedes.big_endian_int,
    'flowControl/MRC': sedes.CountableList(
        sedes.List([sedes.big_endian_int, sedes.big_endian_int, sedes.big_endian_int])),
    'flowControl/MRR': sedes.big_endian_int,
    'announceType': sedes.big_endian_int,
}


class StatusSerializationCodecV2(StatusSerializationCodec):
    item_sedes = STATUS_V2_ITEM_SEDES


class StatusV2(BaseCommand[StatusPayload]):
    protocol_command_id = 0
    serialization_codec = StatusSerializationCodecV2()


class GetProofsV2(GetProofsV1):
    # Same structure as V1 (response structure is what differs)
    protocol_command_id = 15


PROOFS_V2_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
    sedes.CountableList(sedes.raw),
))


class ProofsV2(BaseCommand[ProofsPayloadV2]):
    protocol_command_id = 16
    serialization_codec = RLPCodec(
        sedes=PROOFS_V2_STRUCTURE,
        process_inbound_payload_fn=compose(
            lambda args: ProofsPayloadV2(*args),
        ),
    )
