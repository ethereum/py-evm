import rlp
from rlp import sedes

from eth_typing import (
    Hash32
)
from eth_utils import keccak

from evm.rlp.headers import BlockHeader
from evm.rlp.transactions import BaseTransaction


class ImmutableBlockHeader(BlockHeader):
    """Immutable variant of `BlockHeader` that also caches its RLP representation.

    By doing that we can compute the header's hash only once, significantly improving performance
    when performing a chain sync.
    """
    _hash = None

    @classmethod
    def deserialize(cls, serial, exclude=None, mutable=False, **kwargs):
        obj = super().deserialize(serial, exclude=exclude, mutable=True, **kwargs)
        obj._cached_rlp = rlp.codec.encode_raw(serial)
        return sedes.make_immutable(obj)

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = keccak(self._cached_rlp)
        return self._hash


# This is needed because BaseTransaction has several @abstractmethods, which means it can't be
# instantiated.
class P2PTransaction(rlp.Serializable):
    fields = BaseTransaction.fields.copy()


class BlockBody(rlp.Serializable):
    fields = [
        ('transactions', sedes.CountableList(P2PTransaction)),
        ('uncles', sedes.CountableList(ImmutableBlockHeader))
    ]
