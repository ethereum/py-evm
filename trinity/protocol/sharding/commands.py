from rlp import sedes

from eth.rlp.collations import Collation
from eth.rlp.sedes import (
    hash32,
)

from p2p.protocol import (
    Command,
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
