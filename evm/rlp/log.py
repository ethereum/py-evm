import rlp
from rlp.sedes import (
    CountableList,
    binary,
)

from .sedes import (
    address,
    int32,
)


class Log(rlp.Serializable):
    fields = [
        ('address', address),
        ('topics', CountableList(int32)),
        ('data', binary)
    ]

    def __init__(self, address, topics, data):
        super(Log, self).__init__(address, topics, data)
