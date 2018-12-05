
from typing import (
    Any,
    Iterable,
    Sequence,
    Tuple,
    TypeVar,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_tuple,
)

from eth.utils.blake import (
    blake,
)
from eth.beacon.constants import (
    RAND_BYTES,
    RAND_MAX,
)


TItem = TypeVar('TItem')


@to_tuple
def shuffle(values: Sequence[Any],
            seed: Hash32) -> Iterable[Any]:
    """
    Returns the shuffled ``values`` with seed as entropy.
    Mainly for shuffling active validators in-protocol.

    Spec: https://github.com/ethereum/eth2.0-specs/blob/70cef14a08de70e7bd0455d75cf380eb69694bfb/specs/core/0_beacon-chain.md#helper-functions  # noqa: E501
    """
    values_count = len(values)

    # The range of the RNG places an upper-bound on the size of the list that
    # may be shuffled. It is a logic error to supply an oversized list.
    if values_count >= RAND_MAX:
        raise ValueError(
            "values_count (%s) should less than RAND_MAX (%s)." %
            (values_count, RAND_MAX)
        )

    output = [x for x in values]
    source = seed
    index = 0
    while index < values_count - 1:
        # Re-hash the `source` to obtain a new pattern of bytes.
        source = blake(source)

        # Iterate through the `source` bytes in 3-byte chunks.
        for position in range(0, 32 - (32 % RAND_BYTES), RAND_BYTES):
            # Determine the number of indices remaining in `values` and exit
            # once the last index is reached.
            remaining = values_count - index
            if remaining == 1:
                break

            # Read 3-bytes of `source` as a 24-bit big-endian integer.
            sample_from_source = int.from_bytes(
                source[position:position + RAND_BYTES], 'big'
            )

            # Sample values greater than or equal to `sample_max` will cause
            # modulo bias when mapped into the `remaining` range.
            sample_max = RAND_MAX - RAND_MAX % remaining

            # Perform a swap if the consumed entropy will not cause modulo bias.
            if sample_from_source < sample_max:
                # Select a replacement index for the current index.
                replacement_position = (sample_from_source % remaining) + index
                # Swap the current index with the replacement index.
                (output[index], output[replacement_position]) = (
                    output[replacement_position],
                    output[index]
                )
                index += 1
            else:
                # The sample causes modulo bias. A new sample should be read.
                pass

    return output


def split(values: Sequence[TItem], split_count: int) -> Tuple[Any, ...]:
    """
    Returns the split ``values`` in ``split_count`` pieces in protocol.
    Spec: https://github.com/ethereum/eth2.0-specs/blob/70cef14a08de70e7bd0455d75cf380eb69694bfb/specs/core/0_beacon-chain.md#helper-functions  # noqa: E501
    """
    list_length = len(values)
    return tuple(
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    )
