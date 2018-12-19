import pytest


from eth.beacon.types.attestations import Attestation
from eth.beacon.types.attestation_data import AttestationData
from eth.beacon.types.blocks import BaseBeaconBlock

from eth.constants import (
    ZERO_HASH32,
)

from p2p.peer import (
    MsgBuffer,
)

from trinity.protocol.bcc.commands import (
    BeaconBlocks,
    GetBeaconBlocks,
    AttestationRecords,
)

from .helpers import (
    get_directly_linked_peers,
    empty_body,
    get_genesis_chain_db,
)


@pytest.mark.asyncio
async def test_send_no_blocks(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_blocks((), request_id=5)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == {
        "request_id": 5,
        "blocks": (),
    }


@pytest.mark.asyncio
async def test_send_single_block(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    block = BaseBeaconBlock(
        slot=1,
        parent_root=ZERO_HASH32,
        state_root=ZERO_HASH32,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        signature=(0, 0),
        body=empty_body(),
    )
    alice.sub_proto.send_blocks((block,), request_id=5)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == {
        "request_id": 5,
        "blocks": (block,),
    }


@pytest.mark.asyncio
async def test_send_multiple_blocks(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    blocks = tuple(
        BaseBeaconBlock(
            slot=slot,
            parent_root=ZERO_HASH32,
            state_root=ZERO_HASH32,
            randao_reveal=ZERO_HASH32,
            candidate_pow_receipt_root=ZERO_HASH32,
            signature=(0, 0),
            body=empty_body(),
        )
        for slot in range(3)
    )
    alice.sub_proto.send_blocks(blocks, request_id=5)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, BeaconBlocks)
    assert message.payload == {
        "request_id": 5,
        "blocks": blocks,
    }


@pytest.mark.asyncio
async def test_send_get_blocks_by_slot(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_get_blocks(123, 10, request_id=5)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, GetBeaconBlocks)
    assert message.payload == {
        "request_id": 5,
        "block_slot_or_root": 123,
        "max_blocks": 10,
    }


@pytest.mark.asyncio
async def test_send_get_blocks_by_hash(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_get_blocks(b"\x33" * 32, 15, request_id=5)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, GetBeaconBlocks)
    assert message.payload == {
        "request_id": 5,
        "block_slot_or_root": b"\x33" * 32,
        "max_blocks": 15,
    }


@pytest.mark.asyncio
async def test_send_no_attestations(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    alice.sub_proto.send_attestation_records(())

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == ()


@pytest.mark.asyncio
async def test_send_single_attestation(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    attestation = Attestation(
        data=AttestationData(
            slot=0,
            shard=1,
            beacon_block_root=ZERO_HASH32,
            epoch_boundary_root=ZERO_HASH32,
            shard_block_root=ZERO_HASH32,
            latest_crosslink_root=ZERO_HASH32,
            justified_slot=0,
            justified_block_root=ZERO_HASH32,
        ),
        participation_bitfield=b"\x00\x00\x00",
        custody_bitfield=b"\x00\x00\x00",
    )

    alice.sub_proto.send_attestation_records((attestation,))

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == (attestation,)


@pytest.mark.asyncio
async def test_send_multiple_attestations(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    msg_buffer = MsgBuffer()
    bob.add_subscriber(msg_buffer)

    attestations = tuple(
        Attestation(
            data=AttestationData(
                slot=0,
                shard=1,
                beacon_block_root=ZERO_HASH32,
                epoch_boundary_root=ZERO_HASH32,
                shard_block_root=ZERO_HASH32,
                latest_crosslink_root=ZERO_HASH32,
                justified_slot=0,
                justified_block_root=ZERO_HASH32,
            ),
            participation_bitfield=b"\x00\x00\x00",
            custody_bitfield=b"\x00\x00\x00",
        ) for shard in range(10)
    )

    alice.sub_proto.send_attestation_records(attestations)

    message = await msg_buffer.msg_queue.get()
    assert isinstance(message.command, AttestationRecords)
    assert message.payload == attestations
