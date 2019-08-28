import asyncio
from typing import (
    Tuple,
)

from eth.exceptions import (
    BlockNotFound,
)
from eth_utils.toolz import (
    partition_all,
)
from lahja import (
    BroadcastConfig,
)
import pytest

from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
)
from eth2.beacon.helpers import (
    compute_epoch_of_slot,
)
from eth2.beacon.exceptions import (
    NoCommitteeAssignment,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import validate_attestation
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.factories import (
    BeaconChainFactory,
    index_to_pubkey,
    keymap,
)
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
)
from eth2.beacon.tools.builder.committee_assignment import (
    get_committee_assignment,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)

from trinity.plugins.eth2.beacon.validator import (
    Validator,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
)


override_lengths(XIAO_LONG_BAO_CONFIG)


class FakeNode:
    def __init__(self):
        self.list_beacon_block = []

    async def broadcast_beacon_block(self, block):
        self.list_beacon_block.append(block)

    async def broadcast_attestations(self, attestations):
        pass


async def get_validator(event_loop, event_bus, indices) -> Validator:
    chain = BeaconChainFactory()
    validator_privkeys = {
        index: keymap[index_to_pubkey[index]]
        for index in indices
    }

    def get_ready_attestations_fn():
        return ()

    v = Validator(
        chain=chain,
        p2p_node=FakeNode(),
        validator_privkeys=validator_privkeys,
        get_ready_attestations_fn=get_ready_attestations_fn,
        event_bus=event_bus,
    )
    asyncio.ensure_future(v.run(), loop=event_loop)
    await v.events.started.wait()
    # yield to `validator._run`
    await asyncio.sleep(0)
    return v


async def get_linked_validators(event_loop, event_bus) -> Tuple[Validator, Validator]:
    all_indices = tuple(
        index for index in range(len(keymap))
    )
    global_peer_count = 2
    alice_indices, bob_indices = partition_all(
        len(all_indices) // global_peer_count,
        all_indices
    )
    alice = await get_validator(event_loop, event_bus, alice_indices)
    bob = await get_validator(event_loop, event_bus, bob_indices)
    return alice, bob


def _get_slot_with_validator_selected(candidate_indices, state, config):
    epoch = state.current_epoch(config.SLOTS_PER_EPOCH)

    for index in candidate_indices:
        try:
            committee, shard, slot, is_proposer = get_committee_assignment(
                state,
                config,
                epoch,
                index,
            )
            if is_proposer and slot != 0:
                return slot, index
        except NoCommitteeAssignment:
            continue
    raise Exception(
        "Check the parameters of the genesis state; the above code should return"
        " some proposer if the set of ``candidate_indices`` is big enough."
    )


@pytest.mark.asyncio
async def test_validator_propose_block_succeeds(event_loop, event_bus):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()

    slot, proposer_index = _get_slot_with_validator_selected(
        alice.validator_privkeys,
        state,
        state_machine.config,
    )

    head = alice.chain.get_canonical_head()
    block = await alice.propose_block(
        proposer_index=proposer_index,
        slot=slot,
        state=state,
        state_machine=state_machine,
        head_block=head,
    )

    # test: ensure the proposed block is saved to the chaindb
    assert alice.chain.get_block_by_root(block.signing_root) == block

    # test: ensure that the `canonical_head` changed after proposing
    new_head = alice.chain.get_canonical_head()
    assert new_head != head

    # test: ensure the block is broadcast to its peer
    assert block in alice.p2p_node.list_beacon_block


@pytest.mark.asyncio
async def test_validator_propose_block_fails(event_loop, event_bus):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()

    assert set(alice.validator_privkeys).intersection(set(bob.validator_privkeys)) == set()
    slot, proposer_index = _get_slot_with_validator_selected(
        bob.validator_privkeys,
        state,
        state_machine.config,
    )
    head = alice.chain.get_canonical_head()
    # test: if a non-proposer validator proposes a block, the block validation should fail.
    with pytest.raises(KeyError):
        await alice.propose_block(
            proposer_index=proposer_index,
            slot=slot,
            state=state,
            state_machine=state_machine,
            head_block=head,
        )


@pytest.mark.asyncio
async def test_validator_skip_block(event_loop, event_bus):
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=[0])
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()
    slot = state.slot + 1
    post_state = alice.skip_block(
        slot=slot,
        state=state,
        state_machine=state_machine,
    )
    # test: confirm that no block is imported at the slot
    with pytest.raises(BlockNotFound):
        alice.chain.get_canonical_block_by_slot(slot)
    # test: the state root should change after skipping the block
    assert state.hash_tree_root != post_state.hash_tree_root
    assert state.slot + 1 == post_state.slot


@pytest.mark.asyncio
async def test_validator_handle_slot_tick(event_loop, event_bus, monkeypatch):
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=[0])

    event_first_tick_called = asyncio.Event()
    event_second_tick_called = asyncio.Event()

    async def handle_first_tick(slot):
        event_first_tick_called.set()

    async def handle_second_tick(slot):
        event_second_tick_called.set()

    monkeypatch.setattr(alice, 'handle_first_tick', handle_first_tick)
    monkeypatch.setattr(alice, 'handle_second_tick', handle_second_tick)

    # sleep for `event_bus` ready
    await asyncio.sleep(0.01)

    # First tick
    await event_bus.broadcast(
        SlotTickEvent(
            slot=1,
            elapsed_time=2,
            is_second_tick=False,
        ),
        BroadcastConfig(internal=True),
    )
    await asyncio.wait_for(
        event_first_tick_called.wait(),
        timeout=2,
        loop=event_loop,
    )
    assert not event_second_tick_called.is_set()
    event_first_tick_called.clear()

    # Second tick
    await event_bus.broadcast(
        SlotTickEvent(
            slot=1,
            elapsed_time=2,
            is_second_tick=True,
        ),
        BroadcastConfig(internal=True),
    )
    await asyncio.wait_for(
        event_second_tick_called.wait(),
        timeout=2,
        loop=event_loop,
    )
    assert not event_first_tick_called.is_set()


@pytest.mark.asyncio
async def test_validator_handle_first_tick(event_loop, event_bus, monkeypatch):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()

    # test: `handle_first_tick` should call `propose_block` if the validator get selected
    slot_to_propose, index = _get_slot_with_validator_selected(
        alice.validator_privkeys,
        state,
        state_machine.config,
    )

    is_proposing = None

    async def propose_block(proposer_index, slot, state, state_machine, head_block):
        nonlocal is_proposing
        is_proposing = True

    monkeypatch.setattr(alice, 'propose_block', propose_block)

    await alice.handle_first_tick(slot_to_propose)
    assert is_proposing


@pytest.mark.asyncio
async def test_validator_handle_second_tick(event_loop, event_bus, monkeypatch):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state = alice.chain.get_head_state()

    # test: `handle_second_tick` should call `attest`
    # and skip_block` if `state.slot` is behind latest slot
    is_skipping = None
    is_attesting = None

    def skip_block(slot, state, state_machine):
        nonlocal is_skipping
        is_skipping = True

    async def attest(slot):
        nonlocal is_attesting
        is_attesting = True

    monkeypatch.setattr(alice, 'skip_block', skip_block)
    monkeypatch.setattr(alice, 'attest', attest)

    await alice.handle_second_tick(state.slot + 1)
    assert is_skipping
    assert is_attesting


@pytest.mark.asyncio
async def test_validator_get_committee_assigment(event_loop, event_bus):
    alice_indices = [7]
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=alice_indices)
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()
    epoch = compute_epoch_of_slot(state.slot, state_machine.config.SLOTS_PER_EPOCH)

    assert alice.this_epoch_assignment[alice_indices[0]][0] == -1
    alice._get_this_epoch_assignment(alice_indices[0], epoch)
    assert alice.this_epoch_assignment[alice_indices[0]][0] == epoch


@pytest.mark.asyncio
async def test_validator_attest(event_loop, event_bus, monkeypatch):
    alice_indices = [i for i in range(8)]
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=alice_indices)
    head = alice.chain.get_canonical_head()
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()

    epoch = compute_epoch_of_slot(state.slot, state_machine.config.SLOTS_PER_EPOCH)
    assignment = alice._get_this_epoch_assignment(alice_indices[0], epoch)

    attestations = await alice.attest(assignment.slot)
    assert len(attestations) == 1
    attestation = attestations[0]
    assert get_attestation_data_slot(
        state,
        attestation.data,
        state_machine.config,
    ) == assignment.slot
    assert attestation.data.beacon_block_root == head.signing_root
    assert attestation.data.crosslink.shard == assignment.shard

    # Advance the state and validate the attestation
    config = state_machine.config
    future_state = state_machine.state_transition.apply_state_transition(
        state,
        future_slot=assignment.slot + config.MIN_ATTESTATION_INCLUSION_DELAY,
    )
    validate_attestation(
        future_state,
        attestation,
        config,
    )


@pytest.mark.asyncio
async def test_validator_include_ready_attestations(event_loop, event_bus, monkeypatch):
    # Alice controls all validators
    alice_indices = list(range(8))
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=alice_indices)
    state_machine = alice.chain.get_state_machine()
    state = alice.chain.get_head_state()

    attesting_slot = state.slot + 1
    attestations = await alice.attest(attesting_slot)

    assert len(attestations) > 0

    # Mock `get_ready_attestations_fn` so it returns the attestation alice
    # attested to.
    def get_ready_attestations_fn():
        return attestations
    monkeypatch.setattr(alice, 'get_ready_attestations', get_ready_attestations_fn)

    proposing_slot = attesting_slot + XIAO_LONG_BAO_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY
    proposer_index = _get_proposer_index(
        state.copy(
            slot=proposing_slot,
        ),
        state_machine.config,
    )

    head = alice.chain.get_canonical_head()
    block = await alice.propose_block(
        proposer_index=proposer_index,
        slot=proposing_slot,
        state=state,
        state_machine=state_machine,
        head_block=head,
    )

    # Check that attestation is included in the proposed block.
    assert attestations[0] in block.body.attestations
