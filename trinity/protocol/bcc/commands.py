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
    Slot,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BeaconBlock

from p2p.protocol import (
    Command,
)

from trinity.rlp.sedes import (
    HashOrNumber,
)


class RequestMessage(TypedDict):
    request_id: int


class ResponseMessage(TypedDict):
    request_id: int


class StatusMessage(TypedDict):
    protocol_version: int
    network_id: int
    genesis_root: Hash32
    head_slot: Slot


class Status(Command):
    _cmd_id = 0
    structure = (
        ('protocol_version', sedes.big_endian_int),
        ('network_id', sedes.big_endian_int),
        ('genesis_root', sedes.binary),
        ('head_slot', sedes.big_endian_int),
    )


class GetBeaconBlocksMessage(TypedDict):
    request_id: int
    block_slot_or_root: Union[int, Hash32]
    max_blocks: int


class GetBeaconBlocks(Command):
    _cmd_id = 1
    structure = (
        ('request_id', sedes.big_endian_int),
        ('block_slot_or_root', HashOrNumber()),
        ('max_blocks', sedes.big_endian_int),
    )


class BeaconBlocksMessage(TypedDict):
    request_id: int
    encoded_blocks: Tuple[BeaconBlock, ...]


class BeaconBlocks(Command):
    _cmd_id = 2
    structure = (
        ('request_id', sedes.big_endian_int),
        ('encoded_blocks', sedes.CountableList(sedes.binary)),
    )


class AttestationsMessage(TypedDict):
    encoded_attestations: Tuple[Attestation, ...]


class Attestations(Command):
    _cmd_id = 3
    structure = (
        ('encoded_attestations', sedes.CountableList(sedes.binary)),
    )


class NewBeaconBlockMessage(TypedDict):
    encoded_block: BeaconBlock


class NewBeaconBlock(Command):
    _cmd_id = 4
    structure = (
        ('encoded_block', sedes.binary),
    )
