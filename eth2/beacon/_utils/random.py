
from typing import (
    Iterable,
    Sequence,
    Tuple,
    TypeVar,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from eth2._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    POWER_OF_TWO_NUMBERS,
    MAX_LIST_SIZE,
)


TItem = TypeVar('TItem')


def get_permuted_index(index: int,
                       list_size: int,
                       seed: Hash32,
                       shuffle_round_count: int) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...list_size-1`
    with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    if index >= list_size:
        raise ValidationError(
            f"The given `index` ({index}) should be less than `list_size` ({list_size}"
        )

    if list_size > MAX_LIST_SIZE:
        raise ValidationError(
            f"The given `list_size` ({list_size}) should be equal to or less than "
            f"`MAX_LIST_SIZE` ({MAX_LIST_SIZE}"
        )

    new_index = index
    for round in range(shuffle_round_count):
        pivot = int.from_bytes(
            hash_eth2(seed + round.to_bytes(1, 'little'))[0:8],
            'little',
        ) % list_size

        flip = (pivot - new_index) % list_size
        hash_pos = max(new_index, flip)
        h = hash_eth2(seed + round.to_bytes(1, 'little') + (hash_pos // 256).to_bytes(4, 'little'))
        byte = h[(hash_pos % 256) // 8]
        bit = (byte >> (hash_pos % 8)) % 2
        new_index = flip if bit else new_index

    return new_index


def shuffle(values: Sequence[TItem],
            seed: Hash32,
            shuffle_round_count: int) -> Tuple[TItem, ...]:
    # This uses this *sub-function* to get around this `eth-utils` bug
    # https://github.com/ethereum/eth-utils/issues/152
    return tuple(_shuffle(values, seed, shuffle_round_count))


def _shuffle(values: Sequence[TItem],
             seed: Hash32,
             shuffle_round_count: int) -> Iterable[TItem]:
    """
    Return shuffled indices in a pseudorandom permutation `0...list_size-1` with
    ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    list_size = len(values)

    if list_size > MAX_LIST_SIZE:
        raise ValidationError(
            f"The `list_size` ({list_size}) should be equal to or less than "
            f"`MAX_LIST_SIZE` ({MAX_LIST_SIZE}"
        )

    indices = list(range(list_size))
    for round in range(shuffle_round_count):
        hash_bytes = b''.join(
            [
                hash_eth2(seed + round.to_bytes(1, 'little') + i.to_bytes(4, 'little'))
                for i in range((list_size + 255) // 256)
            ]
        )

        pivot = int.from_bytes(
            hash_eth2(seed + round.to_bytes(1, 'little'))[:8],
            'little',
        ) % list_size
        for i in range(list_size):
            flip = (pivot - indices[i]) % list_size
            hash_position = indices[i] if indices[i] > flip else flip
            byte = hash_bytes[hash_position // 8]
            mask = POWER_OF_TWO_NUMBERS[hash_position % 8]
            if byte & mask:
                indices[i] = flip
            else:
                # not swap
                pass

    for i in indices:
        yield values[i]


def split(values: Sequence[TItem], split_count: int) -> Tuple[Sequence[TItem], ...]:
    """
    Return the split ``values`` in ``split_count`` pieces in protocol.
    Spec: https://github.com/ethereum/eth2.0-specs/blob/70cef14a08de70e7bd0455d75cf380eb69694bfb/specs/core/0_beacon-chain.md#helper-functions  # noqa: E501
    """
    list_length = len(values)
    return tuple(
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    )
