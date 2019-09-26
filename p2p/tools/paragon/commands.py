from rlp import sedes

from p2p.commands import BaseCommand, RLPCodec

from .payloads import (
    BroadcastDataPayload,
    GetSumPayload,
    SumPayload,
)


BROADCAST_DATA_STRUCTURE = sedes.List((
    sedes.binary,
))


class BroadcastData(BaseCommand[BroadcastDataPayload]):
    protocol_command_id = 0
    serialization_codec = RLPCodec(
        sedes=BROADCAST_DATA_STRUCTURE,
        process_inbound_payload_fn=lambda args: BroadcastDataPayload(*args),
    )


GET_SUM_STRUCTURE = sedes.List((
    sedes.big_endian_int,
    sedes.big_endian_int,
))


class GetSum(BaseCommand[GetSumPayload]):
    protocol_command_id = 2
    serialization_codec = RLPCodec(
        sedes=GET_SUM_STRUCTURE,
        process_inbound_payload_fn=lambda args: GetSumPayload(*args),
    )


SUM_STRUCTURE = sedes.List((
    sedes.big_endian_int,
))


class Sum(BaseCommand[SumPayload]):
    protocol_command_id = 3
    serialization_codec = RLPCodec(
        sedes=SUM_STRUCTURE,
        process_inbound_payload_fn=lambda args: SumPayload(*args),
    )
