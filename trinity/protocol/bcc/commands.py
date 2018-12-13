from typing import (
    Union,
)

from rlp import sedes

from mypy_extensions import (
    TypedDict,
)

from eth_typing import (
    Hash32,
)

from p2p.protocol import (
    Command,
)

from trinity.rlp.sedes import (
    HashOrNumber,
)

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.attestation_records import AttestationRecord


class Status(Command):
    _cmd_id = 0
    structure = [
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('genesis_hash', sedes.binary),
        ('best_hash', sedes.binary),
    ]


GetBeaconBlocksMessage = TypedDict("GetBeaconBlocksMessage", {
    "block_slot_or_hash": Union[int, Hash32],
    "max_blocks": int,
})


class GetBeaconBlocks(Command):
    _cmd_id = 1
    structure = [
        ('block_slot_or_hash', HashOrNumber()),
        ('max_blocks', sedes.big_endian_int),
    ]


class BeaconBlocks(Command):
    _cmd_id = 2
    structure = sedes.CountableList(BaseBeaconBlock)


class AttestationRecords(Command):
    _cmd_id = 3
    structure = sedes.CountableList(AttestationRecord)
