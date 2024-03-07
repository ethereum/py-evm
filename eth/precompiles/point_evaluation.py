import hashlib

from ckzg import (
    verify_kzg_proof,
)
from eth_typing import (
    Hash32,
)

from eth.abc import (
    ComputationAPI,
)
from eth.vm.forks.cancun.constants import (
    BLS_MODULUS,
    FIELD_ELEMENTS_PER_BLOB,
    POINT_EVALUATION_PRECOMPILE_GAS,
    VERSIONED_HASH_VERSION_KZG,
)


def kzg_to_versioned_hash(commitment: bytes) -> Hash32:
    return VERSIONED_HASH_VERSION_KZG + hashlib.sha256(commitment).digest()[1:]


def point_evaluation_precompile(computation: ComputationAPI) -> bytes:
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
    assert len(input_) == 192
    versioned_hash = input_[:32]
    z = input_[32:64]
    y = input_[64:96]
    commitment = input_[96:144]
    proof = input_[144:192]

    # Verify commitment matches versioned_hash
    assert kzg_to_versioned_hash(commitment) == versioned_hash

    # Verify KZG proof with z and y in big endian format
    assert verify_kzg_proof(commitment, z, y, proof)

    # Return FIELD_ELEMENTS_PER_BLOB and BLS_MODULUS as padded 32 byte big endian values
    return FIELD_ELEMENTS_PER_BLOB.to_bytes(32, "big") + BLS_MODULUS.to_bytes(32, "big")
