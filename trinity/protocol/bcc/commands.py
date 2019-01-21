from typing import (
    Tuple,
    Union,
)

from rlp import sedes

from mypy_extensions import (
    TypedDict,
)

from eth_typing import (
    Hash32,
)

from eth2.beacon.typing import (
    SlotNumber,
)

from p2p.protocol import (
    Command,
)

from trinity.rlp.sedes import (
    HashOrNumber,
)

from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.attestations import Attestation


class RequestMessage(TypedDict):
    request_id: int


class ResponseMessage(TypedDict):
    request_id: int


class StatusMessage(TypedDict):
    protocol_version: int
    network_id: int
    genesis_hash: Hash32
    head_slot: SlotNumber


class Status(Command):
    _cmd_id = 0
    structure = [
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('genesis_hash', sedes.binary),
        ('head_slot', sedes.big_endian_int),
    ]


class GetBeaconBlocksMessage(TypedDict):
    request_id: int
    block_slot_or_root: Union[int, Hash32]
    max_blocks: int


class GetBeaconBlocks(Command):
    _cmd_id = 1
    structure = [
        ('request_id', sedes.big_endian_int),
        ('block_slot_or_root', HashOrNumber()),
        ('max_blocks', sedes.big_endian_int),
    ]


class BeaconBlocksMessage(TypedDict):
    request_id: int
    blocks: Tuple[BeaconBlock, ...]


class BeaconBlocks(Command):
    _cmd_id = 2
    structure = [
        ('request_id', sedes.big_endian_int),
        ('blocks', sedes.CountableList(BeaconBlock)),
    ]


class AttestationRecords(Command):
    _cmd_id = 3
    structure = sedes.CountableList(Attestation)
