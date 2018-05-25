import logging
from typing import (
    List,
    Tuple,
)

from eth_typing import (
    Hash32,
)

from rlp import sedes

from evm.rlp.collations import Collation
from evm.rlp.sedes import (
    hash32,
)

from p2p.protocol import (
    Command,
    Protocol,
)


class Status(Command):
    _cmd_id = 0


class Collations(Command):
    _cmd_id = 1

    structure = [
        ("request_id", sedes.big_endian_int),
        ("collations", sedes.CountableList(Collation)),
    ]


class GetCollations(Command):
    _cmd_id = 2

    structure = [
        ("request_id", sedes.big_endian_int),
        ("collation_hashes", sedes.CountableList(hash32)),
    ]


class NewCollationHashes(Command):
    _cmd_id = 3

    structure = [
        (
            "collation_hashes_and_periods", sedes.CountableList(
                sedes.List([hash32, sedes.big_endian_int])
            )
        ),
    ]


class ShardingProtocol(Protocol):
    name = "sha"
    version = 0
    _commands = [Status, Collations, GetCollations, NewCollationHashes]
    cmd_length = 4

    logger = logging.getLogger("p2p.sharding.ShardingProtocol")

    def send_handshake(self) -> None:
        cmd = Status(self.cmd_id_offset)
        self.logger.debug("Sending status msg")
        self.send(*cmd.encode([]))

    def send_collations(self, request_id: int, collations: List[Collation]) -> None:
        cmd = Collations(self.cmd_id_offset)
        self.logger.debug("Sending %d collations (request id %d)", len(collations), request_id)
        data = {
            "request_id": request_id,
            "collations": collations,
        }
        self.send(*cmd.encode(data))

    def send_get_collations(self, request_id: int, collation_hashes: List[Hash32]) -> None:
        cmd = GetCollations(self.cmd_id_offset)
        self.logger.debug(
            "Requesting %d collations (request id %d)",
            len(collation_hashes),
            request_id,
        )
        data = {
            "request_id": request_id,
            "collation_hashes": collation_hashes,
        }
        self.send(*cmd.encode(data))

    def send_new_collation_hashes(self,
                                  collation_hashes_and_periods: List[Tuple[Hash32, int]]) -> None:
        cmd = NewCollationHashes(self.cmd_id_offset)
        self.logger.debug(
            "Announcing %d new collations (period %d to %d)",
            len(collation_hashes_and_periods),
            min(period for _, period in collation_hashes_and_periods),
            max(period for _, period in collation_hashes_and_periods)
        )
        data = {
            "collation_hashes_and_periods": collation_hashes_and_periods
        }
        self.send(*cmd.encode(data))
