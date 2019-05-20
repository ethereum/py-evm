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
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.configs import (
    Eth2GenesisConfig,
)
from trinity.config import (
    BeaconChainConfig,
    BeaconGenesisData,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
)
from trinity.plugins.eth2.beacon.validator import (
    Validator,
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


def get_chain_from_genesis(db, index):
    pubkey = index_to_pubkey[index]
    validator_keymap = {pubkey: keymap[pubkey]}
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


async def get_validator(event_loop, event_bus, index) -> Validator:
    chain_db = await helpers.get_chain_db()
    chain = get_chain_from_genesis(chain_db.db, index)
    peer_pool = FakePeerPool()
    validator_privkeys = {index: keymap[index_to_pubkey[index]]}
    v = Validator(
        chain=chain,
        peer_pool=peer_pool,
        validator_privkeys=validator_privkeys,
        genesis_config=Eth2GenesisConfig(XIAO_LONG_BAO_CONFIG),
        event_bus=event_bus,
    )
    asyncio.ensure_future(v.run(), loop=event_loop)
    await v.events.started.wait()
    # yield to `validator._run`
    await asyncio.sleep(0)
    return v


async def get_linked_validators(event_loop, event_bus) -> Tuple[Validator, Validator]:
    alice_index = 0
    bob_index = 1
    alice = await get_validator(event_loop, event_bus, alice_index)
    bob = await get_validator(event_loop, event_bus, bob_index)
    alice.peer_pool.add_peer(bob_index)
    bob.peer_pool.add_peer(alice_index)
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
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, index=0)
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
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, index=0)

    event_new_slot_called = asyncio.Event()

    async def propose_or_skip_block(slot, is_second_tick):
        event_new_slot_called.set()

    monkeypatch.setattr(alice, 'propose_or_skip_block', propose_or_skip_block)

    # sleep for `event_bus` ready
    await asyncio.sleep(0.01)

    await event_bus.broadcast(
        SlotTickEvent(
            slot=1,
            elapsed_time=2,
            is_second_tick=False,
        ),
        BroadcastConfig(internal=True),
    )
    await asyncio.wait_for(
        event_new_slot_called.wait(),
        timeout=2,
        loop=event_loop,
    )


@pytest.mark.asyncio
async def test_validator_propose_or_skip_block(event_loop, event_bus, monkeypatch):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state

    # test: `propose_or_skip_block` should call `propose_block` if the validator get selected
    def is_alice_selected(proposer_index):
        return proposer_index in alice.validator_privkeys

    slot_to_propose, index = _get_slot_with_validator_selected(
        is_desired_proposer_index=is_alice_selected,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )
    alice.latest_proposed_epoch = slot_to_epoch(slot_to_propose, alice.slots_per_epoch) - 1

    is_proposing = None

    def propose_block(proposer_index, slot, state, state_machine, head_block):
        nonlocal is_proposing
        is_proposing = True

    def skip_block(slot, state, state_machine):
        nonlocal is_proposing
        is_proposing = False

    monkeypatch.setattr(alice, 'propose_block', propose_block)
    monkeypatch.setattr(alice, 'skip_block', skip_block)

    await alice.propose_or_skip_block(slot_to_propose, False)
    assert is_proposing

    is_proposing = None

    # test: `propose_or_skip_block` should call `skip_block`.
    def is_not_alice_bob_selected(proposer_index):
        return (
            proposer_index not in alice.validator_privkeys and
            proposer_index not in bob.validator_privkeys
        )

    slot_to_skip, index = _get_slot_with_validator_selected(
        is_desired_proposer_index=is_not_alice_bob_selected,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )

    await alice.propose_or_skip_block(slot_to_skip, is_second_tick=False)
    assert is_proposing is None, "`skip_block` should not be called if `is_second_tick == False`"

    await alice.propose_or_skip_block(slot_to_skip, is_second_tick=True)
    assert is_proposing is False, "`skip_block` should have been called"
