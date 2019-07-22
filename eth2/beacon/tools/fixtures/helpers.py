from typing import (
    Tuple,
    Type,
)

from ssz.tools import (
    to_formatted_dict,
)

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.tools.builder.proposer import (
    advance_to_slot,
)
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)
from eth2.beacon.tools.fixtures.test_case import (
    StateTestCase,
)
from eth2.beacon.types.states import BeaconState


def run_state_execution(test_case: StateTestCase,
                        sm_class: Type[SerenityStateMachine],
                        chaindb: BeaconChainDB,
                        attestation_pool: AttestationPool,
                        state: BeaconState) -> BeaconState:
    chaindb.persist_state(state)
    post_state = state
    post_state, chaindb = apply_advance_to_slot(
        test_case,
        sm_class,
        chaindb,
        attestation_pool,
        post_state,
    )
    post_state, chaindb = apply_blocks(
        test_case,
        sm_class,
        chaindb,
        attestation_pool,
        post_state,
    )
    return post_state


def apply_advance_to_slot(test_case: StateTestCase,
                          sm_class: Type[SerenityStateMachine],
                          chaindb: BeaconChainDB,
                          attestation_pool: AttestationPool,
                          state: BeaconState) -> Tuple[BeaconState, BeaconChainDB]:
    post_state = state.copy()
    sm = sm_class(chaindb, attestation_pool, None, post_state)
    slot = test_case.pre.slot + test_case.slots
    chaindb.persist_state(post_state)
    return advance_to_slot(sm, post_state, slot), chaindb


def apply_blocks(test_case: StateTestCase,
                 sm_class: Type[SerenityStateMachine],
                 chaindb: BeaconChainDB,
                 attestation_pool: AttestationPool,
                 state: BeaconState) -> Tuple[BeaconState, BeaconChainDB]:
    post_state = state.copy()
    for block in test_case.blocks:
        sm = sm_class(chaindb, attestation_pool, None, post_state)
        post_state, _ = sm.import_block(block)
        chaindb.persist_state(post_state)

    return post_state, chaindb


def verify_state(test_case: StateTestCase, post_state: BeaconState) -> None:
    # Use dict diff, easier to see the diff
    dict_post_state = to_formatted_dict(post_state, BeaconState)
    dict_expected_state = to_formatted_dict(test_case.post, BeaconState)
    for key, value in dict_expected_state.items():
        if isinstance(value, list):
            value = tuple(value)
        if dict_post_state[key] != value:
            raise AssertionError(
                f"state.{key} is incorrect:\n"
                f"\tExpected: {value}\n"
                f"\tResult: {dict_post_state[key]}\n"
            )
