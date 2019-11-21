from typing import (
    Any,
    Iterable,
)
from eth_utils import (
    is_bytes,
    to_tuple,
)

import rlp
from rlp.codec import _apply_rlp_cache, consume_item
from rlp.exceptions import DecodingError
from rlp.sedes.lists import is_sequence


@to_tuple
def decode_all(rlp: bytes,
               sedes: rlp.Serializable = None,
               recursive_cache: bool = False,
               **kwargs: Any) -> Iterable[Any]:
    """Decode multiple RLP encoded object.

    If the deserialized result `obj` has an attribute :attr:`_cached_rlp` (e.g. if `sedes` is a
    subclass of :class:`rlp.Serializable`) it will be set to `rlp`, which will improve performance
    on subsequent :func:`rlp.encode` calls. Bear in mind however that `obj` needs to make sure that
    this value is updated whenever one of its fields changes or prevent such changes entirely
    (:class:`rlp.sedes.Serializable` does the latter).

    :param sedes: an object implementing a function ``deserialize(code)`` which will be applied
                  after decoding, or ``None`` if no deserialization should be performed
    :param **kwargs: additional keyword arguments that will be passed to the deserializer
    :param strict: if false inputs that are longer than necessary don't cause an exception
    :returns: the decoded and maybe deserialized Python object
    :raises: :exc:`rlp.DecodingError` if the input string does not end after the root item and
             `strict` is true
    :raises: :exc:`rlp.DeserializationError` if the deserialization fails
    """
    if not is_bytes(rlp):
        raise DecodingError('Can only decode RLP bytes, got type %s' % type(rlp).__name__, rlp)

    end = 0
    rlp_length = len(rlp)

    while rlp_length - end > 0:
        try:
            item, per_item_rlp, end = consume_item(rlp, end)
        except IndexError:
            raise DecodingError('RLP string too short', rlp)
        if sedes:
            obj = sedes.deserialize(item, **kwargs)
            if is_sequence(obj) or hasattr(obj, '_cached_rlp'):
                _apply_rlp_cache(obj, per_item_rlp, recursive_cache)
            yield obj
        else:
            yield item
