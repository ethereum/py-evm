import itertools

from eth_utils.toolz import take

from eth2._utils.funcs import forever
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.types.attestations import Attestation


def mk_attestation(index, sample_attestation_params):
    return Attestation(**sample_attestation_params).copy(custody_bits=(True,) * 128)


def test_iterating_operation_pool(sample_attestation_params):
    some_attestation_params = zip(itertools.count(), forever(sample_attestation_params))
    some_attestations = map(lambda x: mk_attestation(*x), some_attestation_params)

    attestation_count = 20
    attestations = tuple(take(attestation_count, some_attestations))

    pool = AttestationPool()
    for a in attestations:
        pool.add(a)

    for _, a in pool:
        assert a in attestations
