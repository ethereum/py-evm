import asyncio

import pytest

from eth.constants import ZERO_HASH32
from eth.exceptions import BlockNotFound

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody

from trinity.protocol.bcc_libp2p.node import REQ_RESP_HELLO_SSZ
from trinity.protocol.bcc_libp2p.configs import ResponseCode
from trinity.protocol.bcc_libp2p.exceptions import HandshakeFailure, RequestFailure
from trinity.protocol.bcc_libp2p.messages import HelloRequest
from trinity.protocol.bcc_libp2p.utils import read_req, write_resp


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_success(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_failure_invalid_hello_packet(
    nodes_with_chain, monkeypatch, mock_timeout
):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    def _make_hello_packet_with_wrong_fork_version():
        return HelloRequest(
            fork_version=b"\x12\x34\x56\x78"  # version different from another node.
        )

    monkeypatch.setattr(
        nodes[0], "_make_hello_packet", _make_hello_packet_with_wrong_fork_version
    )
    # Test: Handshake fails when sending invalid hello packet.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers
    assert nodes[1].peer_id not in nodes[0].handshaked_peers

    def _make_hello_packet_with_wrong_checkpoint():
        return HelloRequest(
            finalized_root=b"\x78" * 32  # finalized root different from another node.
        )

    monkeypatch.setattr(
        nodes[0], "_make_hello_packet", _make_hello_packet_with_wrong_checkpoint
    )
    # Test: Handshake fails when sending invalid hello packet.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers
    assert nodes[1].peer_id not in nodes[0].handshaked_peers


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_failure_failure_response(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    async def fake_handle_hello(stream):
        await read_req(stream, HelloRequest)
        # The overridden `resp_code` can be anything other than `ResponseCode.SUCCESS`
        await write_resp(stream, "error msg", ResponseCode.INVALID_REQUEST)

    # Mock the handler.
    nodes[1].host.set_stream_handler(REQ_RESP_HELLO_SSZ, fake_handle_hello)
    # Test: Handshake fails when the response is not success.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_request_beacon_blocks_fail(nodes_with_chain, monkeypatch):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    # Test: Can not request beacon block before handshake
    with pytest.raises(RequestFailure):
        await nodes[0].request_beacon_blocks(
            peer_id=nodes[1].peer_id,
            head_block_root=ZERO_HASH32,
            start_slot=0,
            count=1,
            step=1,
        )


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_request_beacon_blocks_on_canonical_chain(nodes_with_chain, monkeypatch):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers

    # Mock up block database
    head_slot = 5
    request_head_block_root = b"\x56" * 32
    head_block = BeaconBlock(
        slot=head_slot,
        parent_root=ZERO_HASH32,
        state_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(),
    )
    blocks = [head_block.copy(slot=slot) for slot in range(5)]
    mock_slot_to_block_db = {
        5: head_block,
        4: blocks[4],
        3: blocks[3],
        2: blocks[2],
        1: blocks[1],
        0: blocks[0],
    }

    def get_block_by_root(root):
        return head_block

    monkeypatch.setattr(nodes[1].chain, "get_block_by_root", get_block_by_root)

    def get_canonical_block_by_slot(slot):
        if slot in mock_slot_to_block_db:
            return mock_slot_to_block_db[slot]
        else:
            raise BlockNotFound

    monkeypatch.setattr(
        nodes[1].chain, "get_canonical_block_by_slot", get_canonical_block_by_slot
    )

    start_slot = 0
    count = 5
    step = 3
    requested_blocks = await nodes[0].request_beacon_blocks(
        peer_id=nodes[1].peer_id,
        head_block_root=request_head_block_root,
        start_slot=start_slot,
        count=count,
        step=step,
    )

    expected_blocks = [
        blocks[start_slot + i * step]
        for i in range(count)
        if start_slot + i * step < len(blocks)
    ]
    assert len(requested_blocks) == len(expected_blocks)
    assert set(requested_blocks) == set(expected_blocks)


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_request_beacon_blocks_invalid_request(nodes_with_chain, monkeypatch):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers

    head_slot = 5
    request_head_block_root = b'\x56' * 32
    head_block = BeaconBlock(
        slot=head_slot,
        parent_root=ZERO_HASH32,
        state_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(),
    )

    def get_block_by_root(root):
        return head_block
    monkeypatch.setattr(nodes[1].chain, "get_block_by_root", get_block_by_root)

    # Test: Can not request blocks with `start_slot` greater than head block slot
    start_slot = 6
    count = 5
    step = 1
    with pytest.raises(RequestFailure):
        await nodes[0].request_beacon_blocks(
            peer_id=nodes[1].peer_id,
            head_block_root=request_head_block_root,
            start_slot=start_slot,
            count=count,
            step=step,
        )


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.parametrize(
    "fork_chain_block_slots, start_slot, count, step, expected_block_slots",
    (
        (range(10), 0, 5, 1, range(5)),
        (range(10), 1, 2, 3, [1, 4]),
        ([0, 2, 3, 7, 8], 0, 4, 2, [0, 2]),
        ([0, 4, 5], 4, 2, 2, [4]),
    ),
)
@pytest.mark.asyncio
async def test_request_beacon_blocks_on_fork_chain(nodes_with_chain,
                                                   monkeypatch,
                                                   fork_chain_block_slots,
                                                   start_slot,
                                                   count,
                                                   step,
                                                   expected_block_slots):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers

    canonical_head_slot = fork_chain_block_slots[-1] + 1
    mock_block = BeaconBlock(
        slot=canonical_head_slot,
        parent_root=ZERO_HASH32,
        state_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(),
    )
    canonical_head = mock_block

    # Mock up fork chain block database
    fork_chain_blocks = []
    for slot in fork_chain_block_slots:
        if len(fork_chain_blocks) == 0:
            fork_chain_blocks.append(mock_block.copy(
                slot=slot,
            ))
        else:
            fork_chain_blocks.append(mock_block.copy(
                slot=slot,
                parent_root=fork_chain_blocks[-1].signing_root,
            ))
    mock_root_to_block_db = {
        block.signing_root: block
        for block in fork_chain_blocks
    }

    def get_block_by_root(root):
        if root in mock_root_to_block_db:
            return mock_root_to_block_db[root]
        else:
            raise BlockNotFound
    monkeypatch.setattr(nodes[1].chain, "get_block_by_root", get_block_by_root)

    def get_canonical_block_by_slot(slot):
        return canonical_head
    monkeypatch.setattr(nodes[1].chain, "get_canonical_block_by_slot", get_canonical_block_by_slot)

    requested_blocks = await nodes[0].request_beacon_blocks(
        peer_id=nodes[1].peer_id,
        head_block_root=fork_chain_blocks[-1].signing_root,
        start_slot=start_slot,
        count=count,
        step=step,
    )

    expected_blocks = [
        block
        for block in fork_chain_blocks
        if block.slot in expected_block_slots
    ]
    assert len(requested_blocks) == len(expected_blocks)
    assert set(requested_blocks) == set(expected_blocks)


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_request_beacon_blocks_on_nonexist_chain(nodes_with_chain, monkeypatch):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers

    request_head_block_root = b'\x56' * 32

    def get_block_by_root(root):
        raise BlockNotFound
    monkeypatch.setattr(nodes[1].chain, "get_block_by_root", get_block_by_root)

    start_slot = 0
    count = 5
    step = 1
    requested_blocks = await nodes[0].request_beacon_blocks(
        peer_id=nodes[1].peer_id,
        head_block_root=request_head_block_root,
        start_slot=start_slot,
        count=count,
        step=step,
    )

    assert len(requested_blocks) == 0
