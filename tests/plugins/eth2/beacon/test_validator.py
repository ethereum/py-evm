import asyncio
import importlib
import logging
import time
from typing import (
    Tuple,
)

from eth_utils.exceptions import ValidationError

from lahja import (
    BroadcastConfig,
)

import pytest

from py_ecc import bls

from eth.exceptions import BlockNotFound

from trinity.config import (
    BeaconChainConfig,
    BeaconGenesisData,
)
from trinity.plugins.eth2.beacon.validator import (
    Validator,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.state_machines.forks.xiao_long_bao.configs import (
    XIAO_LONG_BAO_CONFIG,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_genesis,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.beacon.tools.builder.proposer import (
    _get_proposer_index,
)
from trinity.plugins.eth2.beacon.slot_ticker import (
    NewSlotEvent,
)


helpers = importlib.import_module('tests.core.p2p-proto.bcc.helpers')


NUM_VALIDATORS = 8

privkeys = tuple(int.from_bytes(
    hash_eth2(str(i).encode('utf-8'))[:4], 'big')
    for i in range(NUM_VALIDATORS)
)
index_to_pubkey = {}
keymap = {}  # pub -> priv
for i, k in enumerate(privkeys):
    pubkey = bls.privtopub(k)
    index_to_pubkey[i] = pubkey
    keymap[pubkey] = k

genesis_time = int(time.time())

genesis_state, genesis_block = create_mock_genesis(
    num_validators=NUM_VALIDATORS,
    config=XIAO_LONG_BAO_CONFIG,
    keymap=keymap,
    genesis_block_class=SerenityBeaconBlock,
    genesis_time=genesis_time,
)
genesis_data = BeaconGenesisData(
    genesis_time=genesis_time,
    genesis_slot=XIAO_LONG_BAO_CONFIG.GENESIS_SLOT,
    keymap=keymap,
    num_validators=NUM_VALIDATORS,
)
beacon_chain_config = BeaconChainConfig(chain_name='TestTestTest', genesis_data=genesis_data)
chain_class = beacon_chain_config.beacon_chain_class

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


def get_chain_from_genesis(db):
    return chain_class.from_genesis(
        base_db=db,
        genesis_state=genesis_state,
        genesis_block=genesis_block,
    )


async def get_validator(event_loop, event_bus, index) -> Validator:
    chain_db = await helpers.get_chain_db()
    chain = get_chain_from_genesis(chain_db.db)
    peer_pool = FakePeerPool()
    v = Validator(
        validator_index=index,
        chain=chain,
        peer_pool=peer_pool,
        privkey=keymap[index_to_pubkey[index]],
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


def _get_slot_with_validator_selected(largest_index, start_slot, state, state_machine):
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
        if proposer_index <= largest_index:
            return slot, proposer_index
        slot += 1


@pytest.mark.asyncio
async def test_validator_propose_block_succeeds(caplog, event_loop, event_bus):
    caplog.set_level(logging.DEBUG)
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state

    # keep trying future slots, until either alice or bob is a proposer.
    slot, proposer_index = _get_slot_with_validator_selected(
        largest_index=1,
        start_slot=state.slot + 1,
        state=state,
        state_machine=state_machine,
    )
    v: Validator = None
    peer_index = None
    if proposer_index == alice.validator_index:
        v = alice
        peer_index = bob.validator_index
    elif proposer_index == bob.validator_index:
        v = bob
        peer_index = alice.validator_index
    else:
        # should never enter here...
        assert False
    head = v.chain.get_canonical_head()
    block = v.propose_block(
        slot=slot,
        state=state,
        state_machine=state_machine,
        head_block=head,
    )
    # test: ensure the proposed block is saved to the chaindb
    assert v.chain.get_block_by_root(block.signing_root) == block

    # test: ensure that the `canonical_head` changed after proposing
    new_head = v.chain.get_canonical_head()
    assert new_head != head

    # test: ensure the block is broadcast to its peer
    assert block in v.peer_pool.connected_nodes[peer_index].sub_proto.inbox


@pytest.mark.asyncio
async def test_validator_propose_block_fails(caplog, event_loop, event_bus):
    alice, bob = await get_linked_validators(event_loop=event_loop, event_bus=event_bus)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state
    slot = state.slot + 1

    proposer_index = _get_proposer_index(
        state=state,
        slot=slot,
        config=state_machine.config,
    )
    # select the wrong validator as proposer
    v: Validator = None
    if proposer_index == alice.validator_index:
        v = bob
    else:
        v = alice
    head = v.chain.get_canonical_head()
    # test: if a non-proposer validator proposes a block, the block validation should fail.
    with pytest.raises(ValidationError):
        v.propose_block(
            slot=slot,
            state=state,
            state_machine=state_machine,
            head_block=head,
        )


@pytest.mark.asyncio
async def test_validator_skip_block(caplog, event_loop, event_bus):
    caplog.set_level(logging.DEBUG)
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
async def test_validator_handle_new_slot(caplog, event_loop, event_bus, monkeypatch):
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, index=0)

    event_new_slot_called = asyncio.Event()

    async def new_slot(slot):
        event_new_slot_called.set()

    monkeypatch.setattr(alice, 'new_slot', new_slot)

    # sleep for `event_bus` ready
    await asyncio.sleep(0.01)

    event_bus.broadcast(
        NewSlotEvent(
            slot=1,
            elapsed_time=2,
        ),
        BroadcastConfig(internal=True),
    )
    await asyncio.wait_for(
        event_new_slot_called.wait(),
        timeout=2,
        loop=event_loop,
    )


@pytest.mark.asyncio
async def test_validator_new_slot(caplog, event_loop, event_bus, monkeypatch):
    caplog.set_level(logging.DEBUG)
    alice = await get_validator(event_loop=event_loop, event_bus=event_bus, index=0)
    state_machine = alice.chain.get_state_machine()
    state = state_machine.state
    new_slot = state.slot + 1
    # test: `new_slot` should call `propose_block` if the validator get selected,
    #   else calls `skip_block`.
    index = _get_proposer_index(
        state,
        new_slot,
        state_machine.config,
    )

    is_proposing = None

    def propose_block(slot, state, state_machine, head_block):
        nonlocal is_proposing
        is_proposing = True

    def skip_block(slot, state, state_machine):
        nonlocal is_proposing
        is_proposing = False

    monkeypatch.setattr(alice, 'propose_block', propose_block)
    monkeypatch.setattr(alice, 'skip_block', skip_block)

    await alice.new_slot(new_slot)

    # test: either `propose_block` or `skip_block` should be called.
    assert is_proposing is not None
    if alice.validator_index == index:
        assert is_proposing
    else:
        assert not is_proposing
