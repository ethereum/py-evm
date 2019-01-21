import pytest

import asyncio

from p2p.exceptions import HandshakeFailure

from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from trinity.protocol.bcc.proto import BCCProtocol
from trinity.protocol.bcc.commands import (
    Status,
)

from .helpers import (
    get_directly_linked_peers,
    get_directly_linked_peers_without_handshake,
    get_genesis_chain_db,
)


@pytest.mark.asyncio
async def test_directly_linked_peers_without_handshake():
    alice, bob = await get_directly_linked_peers_without_handshake(
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    assert alice.sub_proto is None
    assert bob.sub_proto is None


@pytest.mark.asyncio
async def test_directly_linked_peers(request, event_loop):
    alice, bob = await get_directly_linked_peers(
        request,
        event_loop,
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    assert isinstance(alice.sub_proto, BCCProtocol)
    assert isinstance(bob.sub_proto, BCCProtocol)

    assert alice.head_slot == bob.context.chain_db.get_canonical_head(BeaconBlock).slot
    assert bob.head_slot == alice.context.chain_db.get_canonical_head(BeaconBlock).slot


@pytest.mark.asyncio
async def test_unidirectional_handshake():
    alice, bob = await get_directly_linked_peers_without_handshake(
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
    alice_chain_db = alice.context.chain_db
    alice_genesis_hash = alice_chain_db.get_canonical_block_by_slot(0, BeaconBlock).hash
    alice_head_slot = alice_chain_db.get_canonical_head(BeaconBlock).slot

    await asyncio.gather(alice.do_p2p_handshake(), bob.do_p2p_handshake())

    await alice.send_sub_proto_handshake()
    cmd, msg = await bob.read_msg()

    assert isinstance(cmd, Status)

    assert msg["protocol_version"] == BCCProtocol.version
    assert msg["network_id"] == alice.context.network_id
    assert msg["genesis_hash"] == alice_genesis_hash
    assert msg["head_slot"] == alice_head_slot

    await bob.process_sub_proto_handshake(cmd, msg)

    assert bob.head_slot == alice_head_slot
    assert alice.head_slot is None

    # stop cleanly
    asyncio.ensure_future(alice.run())
    asyncio.ensure_future(bob.run())
    await asyncio.gather(
        alice.cancel(),
        bob.cancel(),
    )


@pytest.mark.asyncio
async def test_handshake_wrong_network_id():
    alice, bob = await get_directly_linked_peers_without_handshake(
        alice_chain_db=get_genesis_chain_db(),
        bob_chain_db=get_genesis_chain_db(),
    )
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
