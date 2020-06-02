from eth_utils.toolz import (
    merge,
)

from eth import precompiles
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.vm.forks.muir_glacier.computation import (
    MUIR_GLACIER_PRECOMPILES
)
from eth.vm.forks.muir_glacier.computation import (
    MuirGlacierComputation,
)

from .opcodes import BERLIN_OPCODES

BERLIN_PRECOMPILES = merge(
    MUIR_GLACIER_PRECOMPILES,
    {
        force_bytes_to_address(b'\x0a'): precompiles.bls_g1_add,
        force_bytes_to_address(b'\x0b'): precompiles.bls_g1_mul,
        force_bytes_to_address(b'\x0c'): precompiles.bls_g1_multiexp,
        force_bytes_to_address(b'\x0d'): precompiles.bls_g2_add,
        force_bytes_to_address(b'\x0e'): precompiles.bls_g2_mul,
        force_bytes_to_address(b'\x0f'): precompiles.bls_g2_multiexp,
        force_bytes_to_address(b'\x10'): precompiles.bls_pairing,
        force_bytes_to_address(b'\x11'): precompiles.bls_map_fp_to_g1,
        force_bytes_to_address(b'\x12'): precompiles.bls_map_fp2_to_g2,
    }
)


class BerlinComputation(MuirGlacierComputation):
    """
    A class for all execution computations in the ``Berlin`` fork.
    Inherits from :class:`~eth.vm.forks.muir_glacier.MuirGlacierComputation`
    """
    # Override
    opcodes = BERLIN_OPCODES
    _precompiles = BERLIN_PRECOMPILES
