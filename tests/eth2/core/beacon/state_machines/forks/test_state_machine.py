import pytest

from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.state_machines.forks.xiao_long_bao import XiaoLongBaoStateMachine


@pytest.mark.parametrize("sm_klass", (SerenityStateMachine, XiaoLongBaoStateMachine))
def test_sm_class_well_defined(sm_klass):
    state_machine = sm_klass(chaindb=None, attestation_pool=None, slot=None)
    assert state_machine.get_block_class()
