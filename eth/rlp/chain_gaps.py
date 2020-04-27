from typing import Tuple, Iterable

import rlp.sedes
from eth_utils import to_tuple

from eth._utils.numeric import signed_to_unsigned, unsigned_to_signed
from eth.rlp.sedes import uint32
from eth.typing import BlockRange

chain_gaps = rlp.sedes.CountableList(rlp.sedes.List((uint32, uint32)))

# Chain gaps are defined as sequence of markers that define gaps in a chain of connected
# entities. The right hand side of the very last marker is expected to be -1, meaning the gap
# is open-ended. E.g. (500, -1) means: Every header from number 500 upwards is missing.
# [[first_missing, last_missing], ..., [first_missing, -1]]
# Since RLP doesn't define signed integers, we convert the right-hand side from signed_to_unsigned
# before entries are written and convert from unsigned_to_signed after entries are read from disk.


@to_tuple
def _convert_signed_to_unsigned(gaps: Tuple[BlockRange, ...]) -> Iterable[BlockRange]:
        for pair in gaps:
            yield (pair[0], signed_to_unsigned(pair[1]))


@to_tuple
def _convert_unsigned_to_signed(gaps: Tuple[BlockRange, ...]) -> Iterable[BlockRange]:
    for pair in gaps:
        yield (pair[0], unsigned_to_signed(pair[1]))


def encode_chain_gaps(gaps: Tuple[BlockRange, ...]) -> bytes:
    return rlp.encode(
        _convert_signed_to_unsigned(gaps), sedes=chain_gaps
    )


def decode_chain_gaps(gaps: bytes) ->Tuple[BlockRange, ...]:
    val = rlp.decode(gaps, sedes=chain_gaps)
    return _convert_unsigned_to_signed(val)
