from rlp import sedes

from p2p.protocol import (
    Command,
)


class BroadcastData(Command):
    _cmd_id = 0
    structure = (
        ('data', sedes.binary),
    )


class GetSum(Command):
    _cmd_id = 2
    structure = (
        ('a', sedes.big_endian_int),
        ('b', sedes.big_endian_int),
    )


class Sum(Command):
    _cmd_id = 3
    structure = (
        ('result', sedes.big_endian_int),
    )
