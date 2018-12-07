import pytest

import asyncio

from cancel_token import CancelToken

from eth.beacon.types.attestation_records import AttestationRecord
from eth.beacon.types.attestation_signed_data import AttestationSignedData
from eth.db.atomic import AtomicDB
from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.types.blocks import BaseBeaconBlock

from eth.constants import (
    ZERO_HASH32,
)

from p2p import ecies
from p2p.exceptions import HandshakeFailure
from p2p.peer import MsgBuffer

from trinity.protocol.bcc.context import BeaconContext
from trinity.protocol.bcc.peer import (
    BCCPeerFactory,
)
from trinity.protocol.bcc.proto import BCCProtocol
from trinity.protocol.bcc.commands import (
    Status,
    GetBeaconBlocks,
    BeaconBlocks,
    AttestationRecords,
)

from p2p.tools.paragon.helpers import (
    get_directly_linked_peers_without_handshake as _get_directly_linked_peers_without_handshake,
    get_directly_linked_peers as _get_directly_linked_peers,
)


def get_fresh_chain_db():
    db = AtomicDB()
    genesis_block = BaseBeaconBlock(
        slot=0,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        ancestor_hashes=[ZERO_HASH32] * 32,
        state_root=ZERO_HASH32,  # note: not the actual genesis state root
        attestations=[],
        specials=[],
        proposer_signature=None,
    )

    chain_db = BeaconChainDB(db)
    chain_db.persist_block(genesis_block)
    return chain_db


async def _setup_alice_and_bob_factories(alice_chain_db=None, bob_chain_db=None):
    cancel_token = CancelToken('trinity.get_directly_linked_peers_without_handshake')

    #
    # Alice
    #
    if alice_chain_db is None:
        alice_chain_db = get_fresh_chain_db()

    alice_context = BeaconContext(
        chain_db=alice_chain_db,
        network_id=1,
    )

    alice_factory = BCCPeerFactory(
        privkey=ecies.generate_privkey(),
        context=alice_context,
        token=cancel_token,
    )

    #
    # Bob
    #
    if bob_chain_db is None:
        bob_chain_db = get_fresh_chain_db()

    bob_context = BeaconContext(
        chain_db=bob_chain_db,
        network_id=1,
    )

    bob_factory = BCCPeerFactory(
        privkey=ecies.generate_privkey(),
        context=bob_context,
        token=cancel_token,
    )

    return alice_factory, bob_factory


async def get_directly_linked_peers_without_handshake(alice_chain_db=None, bob_chain_db=None):
    alice_factory, bob_factory = await _setup_alice_and_bob_factories(alice_chain_db, bob_chain_db)

    return await _get_directly_linked_peers_without_handshake(
        alice_factory=alice_factory,
        bob_factory=bob_factory,
    )


async def get_directly_linked_peers(request, event_loop, alice_chain_db=None, bob_chain_db=None):
    alice_factory, bob_factory = await _setup_alice_and_bob_factories(
        alice_chain_db,
        bob_chain_db,
    )

    return await _get_directly_linked_peers(
        request,
        event_loop,
        alice_factory=alice_factory,
        bob_factory=bob_factory,
    )


@pytest.mark.asyncio
async def test_directly_linked_peers_without_handshake():
    alice, bob = await get_directly_linked_peers_without_handshake()
    assert alice.sub_proto is None
    assert bob.sub_proto is None


@pytest.mark.asyncio
async def test_directly_linked_peers(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    assert isinstance(alice.sub_proto, BCCProtocol)
    assert isinstance(bob.sub_proto, BCCProtocol)

    assert alice.head_hash == bob.context.chain_db.get_canonical_head().hash
    assert bob.head_hash == alice.context.chain_db.get_canonical_head().hash


@pytest.mark.asyncio
async def test_unidirectional_handshake(request, event_loop):
    alice, bob = await get_directly_linked_peers_without_handshake()
    alice_chain_db = alice.context.chain_db
    alice_genesis_hash = alice_chain_db.get_canonical_block_by_slot(0).hash
    alice_head_hash = alice_chain_db.get_canonical_head().hash

    await asyncio.gather(alice.do_p2p_handshake(), bob.do_p2p_handshake())

    await alice.send_sub_proto_handshake()
    cmd, msg = await bob.read_msg()

    assert isinstance(cmd, Status)

    assert msg["protocol_version"] == BCCProtocol.version
    assert msg["network_id"] == alice.context.network_id
    assert msg["genesis_hash"] == alice_head_hash
    assert msg["best_hash"] == alice_genesis_hash

    await bob.process_sub_proto_handshake(cmd, msg)

    assert bob.head_hash == alice_head_hash
    assert alice.head_hash is None

    # stop cleanly
    asyncio.ensure_future(alice.run())
    asyncio.ensure_future(bob.run())
    await asyncio.gather(
        alice.cancel(),
        bob.cancel(),
    )


@pytest.mark.asyncio
async def test_handshake_wrong_network_id(request, event_loop):
    alice, bob = await get_directly_linked_peers_without_handshake()
    alice.context.network_id += 1
    await asyncio.gather(alice.do_p2p_handshake(), bob.do_p2p_handshake())

    await alice.send_sub_proto_handshake()
    cmd, msg = await bob.read_msg()

    with pytest.raises(HandshakeFailure):
        await bob.process_sub_proto_handshake(cmd, msg)

    # stop cleanly
    asyncio.ensure_future(alice.run())
    asyncio.ensure_future(bob.run())
    await asyncio.gather(
        alice.cancel(),
        bob.cancel(),
    )


@pytest.mark.asyncio
async def test_send_no_blocks(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_blocks(())

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == ()


@pytest.mark.asyncio
async def test_send_single_block(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    block = BaseBeaconBlock(
        slot=1,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        ancestor_hashes=[ZERO_HASH32] * 32,
        state_root=ZERO_HASH32,
        attestations=[],
        specials=[],
        proposer_signature=None,
    )
    alice.sub_proto.send_blocks((block,))

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == (block,)


@pytest.mark.asyncio
async def test_send_multiple_blocks(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    blocks = tuple(
        BaseBeaconBlock(
            slot=slot,
            randao_reveal=ZERO_HASH32,
            candidate_pow_receipt_root=ZERO_HASH32,
            ancestor_hashes=[ZERO_HASH32] * 32,
            state_root=ZERO_HASH32,
            attestations=[],
            specials=[],
            proposer_signature=None,
        )
        for slot in range(3)
    )
    alice.sub_proto.send_blocks(blocks)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == blocks


@pytest.mark.asyncio
async def test_send_get_blocks_by_slot(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_get_blocks(123, 10)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, GetBeaconBlocks)
    assert message.payload == {
        "block_slot_or_hash": 123,
        "max_blocks": 10,
    }


@pytest.mark.asyncio
async def test_send_get_blocks_by_hash(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_get_blocks(b"\x33" * 32, 15)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, GetBeaconBlocks)
    assert message.payload == {
        "block_slot_or_hash": b"\x33" * 32,
        "max_blocks": 15,
    }


@pytest.mark.asyncio
async def test_send_no_attestations(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_attestation_records(())

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == ()


@pytest.mark.asyncio
async def test_send_single_attestation(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    attestation_record = AttestationRecord(
        data=AttestationSignedData(
            slot=0,
            shard=1,
            block_hash=ZERO_HASH32,
            cycle_boundary_hash=ZERO_HASH32,
            shard_block_hash=ZERO_HASH32,
            last_crosslink_hash=ZERO_HASH32,
            justified_slot=0,
            justified_block_hash=ZERO_HASH32,
        ),
        attester_bitfield=b"\x00\x00\x00",
        poc_bitfield=b"\x00\x00\x00",
    )

    alice.sub_proto.send_attestation_records((attestation_record,))

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == (attestation_record,)


@pytest.mark.asyncio
async def test_send_multiple_attestations(request, event_loop):
    alice, bob = await get_directly_linked_peers(request, event_loop)
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    attestation_records = tuple(
        AttestationRecord(
            data=AttestationSignedData(
                slot=0,
                shard=shard,
                block_hash=ZERO_HASH32,
                cycle_boundary_hash=ZERO_HASH32,
                shard_block_hash=ZERO_HASH32,
                last_crosslink_hash=ZERO_HASH32,
                justified_slot=0,
                justified_block_hash=ZERO_HASH32,
            ),
            attester_bitfield=b"\x00\x00\x00",
            poc_bitfield=b"\x00\x00\x00",
        ) for shard in range(10)
    )

    alice.sub_proto.send_attestation_records(attestation_records)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == attestation_records
