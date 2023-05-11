import math

from eth_utils import (
    big_endian_to_int,
)
from eth_utils.toolz import (
    merge,
)

from eth._utils.address import (
    force_bytes_to_address,
)
from eth._utils.numeric import (
    get_highest_bit_index,
)
from eth._utils.padding import (
    zpad_right,
)
from eth.precompiles.modexp import (
    extract_lengths,
    modexp,
)
from eth.vm.forks.berlin import (
    constants,
)
from eth.vm.forks.muir_glacier.computation import (
    MUIR_GLACIER_PRECOMPILES,
    MuirGlacierComputation,
)

from .opcodes import (
    BERLIN_OPCODES,
)


def _calculate_multiplication_complexity(base_length: int, modulus_length: int) -> int:
    max_length = max(base_length, modulus_length)
    words = math.ceil(max_length / 8)
    return words**2


def _calculate_iteration_count(
    exponent_length: int, first_32_exponent_bytes: bytes
) -> int:
    first_32_exponent = big_endian_to_int(first_32_exponent_bytes)

    highest_bit_index = get_highest_bit_index(first_32_exponent)

    if exponent_length <= 32:
        iteration_count = highest_bit_index
    else:
        iteration_count = highest_bit_index + (8 * (exponent_length - 32))

    return max(iteration_count, 1)


def _compute_modexp_gas_fee_eip_2565(data: bytes) -> int:
    base_length, exponent_length, modulus_length = extract_lengths(data)

    base_end_idx = 96 + base_length
    exponent_end_idx = base_end_idx + exponent_length

    first_32_exponent_bytes = zpad_right(
        data[base_end_idx:exponent_end_idx],
        to_size=min(exponent_length, 32),
    )[:32]
    iteration_count = _calculate_iteration_count(
        exponent_length,
        first_32_exponent_bytes,
    )

    multiplication_complexity = _calculate_multiplication_complexity(
        base_length, modulus_length
    )
    return max(
        200,
        multiplication_complexity
        * iteration_count
        // constants.GAS_MOD_EXP_QUADRATIC_DENOMINATOR_EIP_2565,
    )


BERLIN_PRECOMPILES = merge(
    MUIR_GLACIER_PRECOMPILES,
    {
        force_bytes_to_address(b"\x05"): modexp(
            gas_calculator=_compute_modexp_gas_fee_eip_2565
        )
    },
)


class BerlinComputation(MuirGlacierComputation):
    """
    A class for all execution *message* computations in the ``Berlin`` fork.
    Inherits from :class:`~eth.vm.forks.muir_glacier.MuirGlacierComputation`
    """

    # Override
    opcodes = BERLIN_OPCODES
    _precompiles = BERLIN_PRECOMPILES
