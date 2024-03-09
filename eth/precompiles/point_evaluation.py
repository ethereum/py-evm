import hashlib
import os

from ckzg import (
    load_trusted_setup,
    verify_kzg_proof,
)
from eth_typing import (
    Hash32,
)

from eth.abc import (
    ComputationAPI,
)
from eth.exceptions import (
    VMError,
)
from eth.vm.forks.cancun.constants import (
    BLS_MODULUS,
    FIELD_ELEMENTS_PER_BLOB,
    POINT_EVALUATION_PRECOMPILE_GAS,
    VERSIONED_HASH_VERSION_KZG,
)

# load path from ../_utils/kzg_trusted_setup.txt
TRUSTED_SETUP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "_utils", "kzg_trusted_setup.txt"
)


def kzg_to_versioned_hash(commitment: bytes) -> Hash32:
    return VERSIONED_HASH_VERSION_KZG + hashlib.sha256(commitment).digest()[1:]


def point_evaluation_precompile(computation: ComputationAPI) -> ComputationAPI:
    """
    Verify p(z) = y given commitment that corresponds to the polynomial p(x) and a KZG
    proof. Also verify that the provided commitment matches the provided versioned_hash.
    """
    computation.consume_gas(
        POINT_EVALUATION_PRECOMPILE_GAS, reason="Point Evaluation Precompile"
    )

    input_ = computation.msg.data_as_bytes

    # The data is encoded as follows: versioned_hash | z | y | commitment | proof
    # with z and y being padded 32 byte big endian values
    try:
        assert len(input_) == 192
    except AssertionError:
        raise VMError("Point evaluation invalid input length.")

    versioned_hash = input_[:32]
    z = input_[32:64]
    y = input_[64:96]
    commitment = input_[96:144]
    proof = input_[144:192]

    # Verify commitment matches versioned_hash
    try:
        assert kzg_to_versioned_hash(commitment) == versioned_hash
    except AssertionError:
        raise VMError("Point evaluation commitment does not match versioned hash.")

    # Verify KZG proof with z and y in big endian format
    try:
        assert verify_kzg_proof(
            commitment, z, y, proof, load_trusted_setup(TRUSTED_SETUP_PATH)
        )
    except (AssertionError, RuntimeError):
        # RuntimeError is raised when the KZG proof verification fails within the C code
        # from the method itself
        raise VMError("Point evaluation KZG proof verification failed.")

    # Return FIELD_ELEMENTS_PER_BLOB and BLS_MODULUS as padded 32 byte big endian values
    computation.output = FIELD_ELEMENTS_PER_BLOB.to_bytes(
        32, "big"
    ) + BLS_MODULUS.to_bytes(32, "big")

    return computation
