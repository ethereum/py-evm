from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.state_machines.forks.skeleton_lake import SkeletonLakeStateMachine


def test_serenity_state_machine_class_well_defined(genesis_fork_choice_context):
    state_machine = SerenityStateMachine(
        chaindb=None, fork_choice_context=genesis_fork_choice_context
    )
    assert state_machine.get_block_class()


def test_skeleton_lake_state_machine_class_well_defined():
    state_machine = SkeletonLakeStateMachine(chaindb=None)
    assert state_machine.get_block_class()
