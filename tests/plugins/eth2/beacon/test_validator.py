import asyncio
from typing import (
    Tuple,
)

from eth.exceptions import (
    BlockNotFound,
)
from lahja import (
    BroadcastConfig,
)
import pytest

from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import validate_attestation
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.configs import CommitteeConfig

from trinity.config import (
    BeaconChainConfig,
    BeaconGenesisData,
)
from trinity.plugins.eth2.beacon.validator import (
    Validator,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
)

from .helpers import (
    genesis_block,
    genesis_state,
    helpers,
    index_to_pubkey,
    keymap,
)

override_vector_lengths(XIAO_LONG_BAO_CONFIG)


class FakeProtocol:
    def __init__(self):
        self.inbox = []

    def send_new_block(self, block):
        self.inbox.append(block)


class FakePeer:
    def __init__(self):
        self.sub_proto = FakeProtocol()


class FakePeerPool:
    def __init__(self):
        self.connected_nodes = {}

    def add_peer(self, index):
        self.connected_nodes[index] = FakePeer()


def get_chain_from_genesis(db, indices):
    # pubkey -> privkey map
    validator_keymap = {
        index_to_pubkey[index]: keymap[index_to_pubkey[index]]
        for index in indices
    }
    genesis_data = BeaconGenesisData(
        genesis_time=genesis_state.genesis_time,
        state=genesis_state,
        validator_keymap=validator_keymap,
    )
    beacon_chain_config = BeaconChainConfig(chain_name='TestTestTest', genesis_data=genesis_data)
    chain_class = beacon_chain_config.beacon_chain_class
    return chain_class.from_genesis(
        base_db=db,
        genesis_state=genesis_state,
        genesis_block=genesis_block,
        genesis_config=beacon_chain_config.genesis_config,
    )


async def get_validator(event_loop, event_bus, indices) -> Validator:
    chain_db = await helpers.get_chain_db()
    chain = get_chain_from_genesis(chain_db.db, indices)
    peer_pool = FakePeerPool()
    validator_privkeys = {
        index: keymap[index_to_pubkey[index]]
        for index in indices
    }
    v = Validator(
        chain=chain,
        peer_pool=peer_pool,
        validator_privkeys=validator_privkeys,
        event_bus=event_bus,
    )
    asyncio.ensure_future(v.run(), loop=event_loop)
    await v.events.started.wait()
    # yield to `validator._run`
    await asyncio.sleep(0)
    return v


async def get_linked_validators(event_loop, event_bus) -> Tuple[Validator, Validator]:
    alice_indices = [0]
    bob_indices = [1]
    alice = await get_validator(event_loop, event_bus, alice_indices)
    bob = await get_validator(event_loop, event_bus, bob_indices)
    alice.peer_pool.add_peer(bob_indices[0])
    bob.peer_pool.add_peer(alice_indices[0])
    return alice, bob


def _get_slot_with_validator_selected(is_desired_proposer_index, start_slot, state, state_machine):
    slot = start_slot
    num_trials = 1000
    while True:
        if (slot - start_slot) > num_trials:
            raise Exception("Failed to find a slot where we have validators selected as a proposer")
        proposer_index = _get_proposer_index(
            state,
            slot,
            state_machine.config,
        )
        if is_desired_proposer_index(proposer_index):
            return slot, proposer_index
        slot += 1


@pytest.mark.asyncio
async def test_validator_propose_block_succeeds(event_loop, event_bus):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state

    # keep trying future slots, until alice is a proposer.
    def is_desired_proposer_index(proposer_index):
        if proposer_index in alice.validator_privkeys:
            return True
        return False

    slot, proposer_index = _get_slot_with_validator_selected(
        is_desired_proposer_index=is_desired_proposer_index,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )

    head = alice.chain.get_canonical_head()
    block = alice.propose_block(
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
    peer = tuple(alice.peer_pool.connected_nodes.values())[0]
    assert block in peer.sub_proto.inbox


@pytest.mark.asyncio
async def test_validator_propose_block_fails(event_loop, event_bus):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state
    slot = state.slot + 1

    # keep trying future slots, until bob is a proposer.
    def is_desired_proposer_index(proposer_index):
        if proposer_index not in alice.validator_privkeys:
            return True
        return False

    slot, proposer_index = _get_slot_with_validator_selected(
        is_desired_proposer_index=is_desired_proposer_index,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )
    head = alice.chain.get_canonical_head()
    # test: if a non-proposer validator proposes a block, the block validation should fail.
    with pytest.raises(KeyError):
        alice.propose_block(
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
    state = state_machine.state
    slot = state.slot + 1
    root_post_state = alice.skip_block(
        slot=slot,
        state=state,
        state_machine=state_machine,
    )
    # test: confirm that no block is imported at the slot
    with pytest.raises(BlockNotFound):
        alice.chain.get_canonical_block_by_slot(slot)
    # test: the state root should change after skipping the block
    assert state.root != root_post_state
    # TODO: more tests


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
    state = state_machine.state

    # test: `handle_first_tick` should call `attest` and
    # `propose_block` if the validator get selected
    def is_alice_selected(proposer_index):
        return proposer_index in alice.validator_privkeys

    slot_to_propose, index = _get_slot_with_validator_selected(
        is_desired_proposer_index=is_alice_selected,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )

    is_proposing = None
    is_attesting = None

    def propose_block(proposer_index, slot, state, state_machine, head_block):
        nonlocal is_proposing
        is_proposing = True

    async def attest(slot):
        nonlocal is_attesting
        is_attesting = True

    monkeypatch.setattr(alice, 'propose_block', propose_block)
    monkeypatch.setattr(alice, 'attest', attest)

    await alice.handle_first_tick(slot_to_propose)
    assert is_proposing
    assert is_attesting


@pytest.mark.asyncio
async def test_validator_handle_second_tick(event_loop, event_bus, monkeypatch):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state

    # test: `handle_second_tick` should call `skip_block` if `state.slot` is behind latest slot
    is_skipping = None

    def skip_block(slot, state, state_machine):
        nonlocal is_skipping
        is_skipping = True

    monkeypatch.setattr(alice, 'skip_block', skip_block)

    await alice.handle_second_tick(state.slot + 1)
    assert is_skipping


@pytest.mark.asyncio
async def test_validator_get_committee_assigment(event_loop, event_bus):
    alice_indices = [7]
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=alice_indices)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state
    epoch = slot_to_epoch(state.slot, state_machine.config.SLOTS_PER_EPOCH)

    assert alice.this_epoch_assignment[alice_indices[0]][0] == -1
    alice._get_this_epoch_assignment(alice_indices[0], epoch)
    assert alice.this_epoch_assignment[alice_indices[0]][0] == epoch


@pytest.mark.asyncio
async def test_validator_attest(event_loop, event_bus, monkeypatch):
    alice_indices = [i for i in range(8)]
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, indices=alice_indices)
    head = alice.chain.get_canonical_head()
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state

    epoch = slot_to_epoch(state.slot, state_machine.config.SLOTS_PER_EPOCH)
    assignment = alice._get_this_epoch_assignment(alice_indices[0], epoch)

    attestations = await alice.attest(assignment.slot)
    assert len(attestations) == 1
    attestation = attestations[0]
    assert attestation.data.slot == assignment.slot
    assert attestation.data.beacon_block_root == head.signing_root
    assert attestation.data.shard == assignment.shard

    # Advance the state and validate the attestation
    config = state_machine.config
    future_state = state_machine.state_transition.apply_state_transition_without_block(
        state,
        assignment.slot + config.MIN_ATTESTATION_INCLUSION_DELAY,
    )
    validate_attestation(
        future_state,
        attestation,
        config.MIN_ATTESTATION_INCLUSION_DELAY,
        config.SLOTS_PER_HISTORICAL_ROOT,
        CommitteeConfig(config),
    )
