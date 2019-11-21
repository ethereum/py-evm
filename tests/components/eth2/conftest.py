import pytest
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from eth2.beacon.state_machines.forks.skeleton_lake.config import (
    MINIMAL_SERENITY_CONFIG,
)


# SSZ
@pytest.fixture(scope="function", autouse=True)
def override_ssz_lengths():
    override_lengths(MINIMAL_SERENITY_CONFIG)
