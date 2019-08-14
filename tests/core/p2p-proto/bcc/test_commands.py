import pytest

import ssz

from async_generator import asynccontextmanager

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
)
from eth2.beacon.types.crosslinks import Crosslink

from p2p.peer import (
    MsgBuffer,
)

from trinity.protocol.bcc.commands import (
    BeaconBlocks,
    GetBeaconBlocks,
    Attestations,
)

from eth2.beacon.constants import EMPTY_SIGNATURE
from trinity.tools.bcc_factories import BCCPeerPairFactory


@asynccontextmanager
async def get_command_setup():
    async with BCCPeerPairFactory() as (alice, bob):
        msg_buffer = MsgBuffer()
        bob.add_subscriber(msg_buffer)

        yield alice, msg_buffer


@pytest.mark.asyncio
async def test_send_no_blocks():
    async with get_command_setup() as (alice, msg_buffer):
        request_id = 5
        alice.sub_proto.send_blocks((), request_id=request_id)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, BeaconBlocks)
        assert message.payload == {
            "request_id": request_id,
            "encoded_blocks": (),
        }


@pytest.mark.asyncio
async def test_send_single_block():
    async with get_command_setup() as (alice, msg_buffer):

        request_id = 5
        block = BeaconBlock(
            slot=1,
            parent_root=ZERO_HASH32,
            state_root=ZERO_HASH32,
            signature=EMPTY_SIGNATURE,
            body=BeaconBlockBody(),
        )
        alice.sub_proto.send_blocks((block,), request_id=request_id)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, BeaconBlocks)
        assert message.payload == {
            "request_id": request_id,
            "encoded_blocks": (ssz.encode(block),),
        }


@pytest.mark.asyncio
async def test_send_multiple_blocks():
    async with get_command_setup() as (alice, msg_buffer):

        request_id = 5
        blocks = tuple(
            BeaconBlock(
                slot=slot,
                parent_root=ZERO_HASH32,
                state_root=ZERO_HASH32,
                signature=EMPTY_SIGNATURE,
                body=BeaconBlockBody(),
            )
            for slot in range(3)
        )
        alice.sub_proto.send_blocks(blocks, request_id=request_id)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, BeaconBlocks)
        assert message.payload == {
            "request_id": request_id,
            "encoded_blocks": tuple(ssz.encode(block) for block in blocks),
        }


@pytest.mark.asyncio
async def test_send_get_blocks_by_slot():
    async with get_command_setup() as (alice, msg_buffer):

        request_id = 5
        alice.sub_proto.send_get_blocks(123, 10, request_id=request_id)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, GetBeaconBlocks)
        assert message.payload == {
            "request_id": request_id,
            "block_slot_or_root": 123,
            "max_blocks": 10,
        }


@pytest.mark.asyncio
async def test_send_get_blocks_by_hash():
    async with get_command_setup() as (alice, msg_buffer):

        request_id = 5
        alice.sub_proto.send_get_blocks(b"\x33" * 32, 15, request_id=request_id)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, GetBeaconBlocks)
        assert message.payload == {
            "request_id": request_id,
            "block_slot_or_root": b"\x33" * 32,
            "max_blocks": 15,
        }


@pytest.mark.asyncio
async def test_send_no_attestations():
    async with get_command_setup() as (alice, msg_buffer):

        alice.sub_proto.send_attestation_records(())

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, Attestations)
        assert message.payload == {
            "encoded_attestations": (),
        }


@pytest.mark.asyncio
async def test_send_single_attestation():
    async with get_command_setup() as (alice, msg_buffer):

        attestation = Attestation(
            aggregation_bits=b"\x00\x00\x00",
            data=AttestationData(
                crosslink=Crosslink(
                    shard=1,
                )
            ),
            custody_bits=b"\x00\x00\x00",
        )

        alice.sub_proto.send_attestation_records((attestation,))

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, Attestations)
        assert message.payload["encoded_attestations"] == (ssz.encode(attestation),)


@pytest.mark.asyncio
async def test_send_multiple_attestations():
    async with get_command_setup() as (alice, msg_buffer):

        attestations = tuple(
            Attestation(
                aggregation_bits=b"\x00\x00\x00",
                data=AttestationData(
                    crosslink=Crosslink(
                        shard=shard,
                    )
                ),
                custody_bits=b"\x00\x00\x00",
            ) for shard in range(10)
        )

        alice.sub_proto.send_attestation_records(attestations)

        message = await msg_buffer.msg_queue.get()
        assert isinstance(message.command, Attestations)
        assert message.payload["encoded_attestations"] == tuple(
            ssz.encode(attestation) for attestation in attestations)
