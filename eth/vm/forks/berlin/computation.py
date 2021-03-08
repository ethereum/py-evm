import math

from eth_utils.toolz import (
    merge,
)

from eth.abc import (
    MessageAPI,
    StateAPI,
    TransactionContextAPI,
)
from eth.precompiles.modexp import (
    compute_adjusted_exponent_length,
    extract_lengths,
    modexp,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth._utils.padding import (
    zpad_right,
)

from eth.vm.forks.berlin import constants

from eth.vm.forks.muir_glacier.computation import (
    MUIR_GLACIER_PRECOMPILES
)
from eth.vm.forks.muir_glacier.computation import (
    MuirGlacierComputation,
)

from .opcodes import BERLIN_OPCODES


def _calculate_multiplication_complexity(base_length: int, modulus_length: int) -> int:
    max_length = max(base_length, modulus_length)
    words = math.ceil(max_length / 8)
    return words**2


def _compute_modexp_gas_fee_eip_2565(data: bytes) -> int:
    base_length, exponent_length, modulus_length = extract_lengths(data)

    base_end_idx = 96 + base_length
    exponent_end_idx = base_end_idx + exponent_length

    exponent_bytes = zpad_right(
        data[base_end_idx:exponent_end_idx],
        to_size=exponent_length,
    )

    multiplication_complexity = _calculate_multiplication_complexity(base_length, modulus_length)
    iteration_count = compute_adjusted_exponent_length(exponent_length, exponent_bytes)
    return max(200,
               multiplication_complexity * iteration_count
               // constants.GAS_MOD_EXP_QUADRATIC_DENOMINATOR_EIP_2565)


BERLIN_PRECOMPILES = merge(
    MUIR_GLACIER_PRECOMPILES,
    {force_bytes_to_address(b'\x05'): modexp(gas_calculator=_compute_modexp_gas_fee_eip_2565)},
)


class BerlinComputation(MuirGlacierComputation):
    """
    A class for all execution computations in the ``Berlin`` fork.
    Inherits from :class:`~eth.vm.forks.muir_glacier.MuirGlacierComputation`
    """
    # Override
    opcodes = BERLIN_OPCODES
    _precompiles = BERLIN_PRECOMPILES

    def __init__(self,
                 state: StateAPI,
                 message: MessageAPI,
                 transaction_context: TransactionContextAPI) -> None:
        precompile_addresses = self.precompiles.keys()
        for addr in precompile_addresses:
            state.add_account_accessed(addr)
        super().__init__(state, message, transaction_context)
