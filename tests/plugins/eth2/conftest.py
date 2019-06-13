import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)


# SSZ
@pytest.fixture(scope="function", autouse=True)
def override_lengths():
    override_vector_lengths(XIAO_LONG_BAO_CONFIG)


@pytest.fixture
def mock_attestation():
    return Attestation(
        aggregation_bitfield=b'\x12' * 16,
        data=AttestationData(
            slot=XIAO_LONG_BAO_CONFIG.GENESIS_SLOT + 1,
            beacon_block_root=ZERO_HASH32,
            source_epoch=XIAO_LONG_BAO_CONFIG.GENESIS_EPOCH,
            source_root=ZERO_HASH32,
            target_root=ZERO_HASH32,
            shard=0,
            previous_crosslink=Crosslink(),
            crosslink_data_root=ZERO_HASH32,
        ),
        custody_bitfield=b'\x34' * 16,
        aggregate_signature=b'\x56' * 96,
    )
