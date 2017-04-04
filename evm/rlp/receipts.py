import rlp
from rlp.sedes import (
    big_endian_int,
    CountableList,
)

from .sedes import (
    trie_root,
    int256,
)

from .logs import Log


class Receipt(rlp.Serializable):

    fields = [
        ('state_root', trie_root),
        ('gas_used', big_endian_int),
        ('bloom', int256),
        ('logs', CountableList(Log))
    ]

    def __init__(self, state_root, gas_used, logs, bloom):
        super(Receipt, self).__init__(state_root, gas_used, logs, bloom)
