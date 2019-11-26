import pytest

from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.state_machines.forks.skeleton_lake import SkeletonLakeStateMachine


@pytest.mark.parametrize("sm_klass", (SerenityStateMachine, SkeletonLakeStateMachine))
def test_sm_class_well_defined(sm_klass):
    state_machine = sm_klass(chaindb=None, attestation_pool=None)
    assert state_machine.get_block_class()
