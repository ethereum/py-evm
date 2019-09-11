import asyncio

from eth.constants import ZERO_HASH32
from eth.exceptions import BlockNotFound
from eth.validation import validate_word
import pytest

from eth2.beacon.constants import EMPTY_SIGNATURE
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from trinity.protocol.bcc_libp2p.configs import GoodbyeReasonCode, ResponseCode
from trinity.protocol.bcc_libp2p.exceptions import HandshakeFailure, RequestFailure
from trinity.protocol.bcc_libp2p.messages import HelloRequest
from trinity.protocol.bcc_libp2p.node import REQ_RESP_HELLO_SSZ
from trinity.protocol.bcc_libp2p.utils import read_req, write_resp
from trinity.tools.bcc_factories import ConnectionPairFactory, NodeFactory


@pytest.mark.asyncio
async def test_hello_success():
    async with ConnectionPairFactory(say_hello=False) as (alice, bob):
        await alice.say_hello(bob.peer_id)
        await asyncio.sleep(0.01)
        assert bob.peer_id in alice.handshaked_peers
        assert alice.peer_id in bob.handshaked_peers


@pytest.mark.asyncio
async def test_hello_failure_invalid_hello_packet(monkeypatch, mock_timeout):
    async with ConnectionPairFactory(say_hello=False) as (alice, bob):

        def _make_hello_packet_with_wrong_fork_version():
            return HelloRequest(
                fork_version=b"\x12\x34\x56\x78"  # version different from another node.
            )

        monkeypatch.setattr(
            alice, "_make_hello_packet", _make_hello_packet_with_wrong_fork_version
        )
        # Test: Handshake fails when sending invalid hello packet.
        with pytest.raises(HandshakeFailure):
            await alice.say_hello(bob.peer_id)
        await asyncio.sleep(0.01)
        assert alice.peer_id not in bob.handshaked_peers
        assert bob.peer_id not in alice.handshaked_peers

        def _make_hello_packet_with_wrong_checkpoint():
            return HelloRequest(
                finalized_root=b"\x78"
                * 32  # finalized root different from another node.
            )

        monkeypatch.setattr(
            alice, "_make_hello_packet", _make_hello_packet_with_wrong_checkpoint
        )
        # Test: Handshake fails when sending invalid hello packet.
        with pytest.raises(HandshakeFailure):
            await alice.say_hello(bob.peer_id)
        await asyncio.sleep(0.01)
        assert alice.peer_id not in bob.handshaked_peers
        assert bob.peer_id not in alice.handshaked_peers


@pytest.mark.asyncio
async def test_hello_failure_failure_response():
    async with ConnectionPairFactory(say_hello=False) as (alice, bob):

        async def fake_handle_hello(stream):
            await read_req(stream, HelloRequest)
            # The overridden `resp_code` can be anything other than `ResponseCode.SUCCESS`
            await write_resp(stream, "error msg", ResponseCode.INVALID_REQUEST)

        # Mock the handler.
        bob.host.set_stream_handler(REQ_RESP_HELLO_SSZ, fake_handle_hello)
        # Test: Handshake fails when the response is not success.
        with pytest.raises(HandshakeFailure):
            await alice.say_hello(bob.peer_id)
        await asyncio.sleep(0.01)
        assert alice.peer_id not in bob.handshaked_peers


@pytest.mark.asyncio
async def test_goodbye():
    async with ConnectionPairFactory() as (alice, bob):
        await alice.say_goodbye(bob.peer_id, GoodbyeReasonCode.FAULT_OR_ERROR)
        await asyncio.sleep(0.01)
        assert bob.peer_id not in alice.handshaked_peers
        assert alice.peer_id not in bob.handshaked_peers


@pytest.mark.asyncio
async def test_request_beacon_blocks_fail():
    async with ConnectionPairFactory(say_hello=False) as (alice, bob):
        # Test: Can not request beacon block before handshake
        with pytest.raises(RequestFailure):
            await alice.request_beacon_blocks(
                peer_id=bob.peer_id,
                head_block_root=ZERO_HASH32,
                start_slot=0,
                count=1,
                step=1,
            )

        # Test: Can not request recent beacon block before handshake
        with pytest.raises(RequestFailure):
            await alice.request_recent_beacon_blocks(
                peer_id=bob.peer_id, block_roots=[b"\x12" * 32]
            )


@pytest.mark.parametrize(
    "db_block_slots, slot_of_requested_blocks, expected_block_slots",
    (
        (range(5), [0, 2, 4], [0, 2, 4]),
        ([1, 3, 5], [0, 2, 4], []),
        ([2, 4], range(5), [2, 4]),
    ),
)
@pytest.mark.asyncio
async def test_get_blocks_from_canonical_chain_by_slot(
    monkeypatch, db_block_slots, slot_of_requested_blocks, expected_block_slots
):
    node = NodeFactory()

    # Mock up block database
    mock_slot_to_block_db = {
        slot: BeaconBlock(
            slot=slot,
            parent_root=ZERO_HASH32,
            state_root=ZERO_HASH32,
            signature=EMPTY_SIGNATURE,
            body=BeaconBlockBody(),
        )
        for slot in db_block_slots
    }

    def get_canonical_block_by_slot(slot):
        if slot in mock_slot_to_block_db:
            return mock_slot_to_block_db[slot]
        else:
            raise BlockNotFound

    monkeypatch.setattr(
        node.chain, "get_canonical_block_by_slot", get_canonical_block_by_slot
    )

    result_blocks = node._get_blocks_from_canonical_chain_by_slot(
        slot_of_requested_blocks=slot_of_requested_blocks
    )

    expected_blocks = [mock_slot_to_block_db[slot] for slot in expected_block_slots]
    assert len(result_blocks) == len(expected_blocks)
    assert set(result_blocks) == set(expected_blocks)


@pytest.mark.asyncio
async def test_request_beacon_blocks_invalid_request(monkeypatch):
    async with ConnectionPairFactory() as (alice, bob):

        head_slot = 1
        request_head_block_root = b"\x56" * 32
        head_block = BeaconBlock(
            slot=head_slot,
            parent_root=ZERO_HASH32,
            state_root=ZERO_HASH32,
            signature=EMPTY_SIGNATURE,
            body=BeaconBlockBody(),
        )

        # TEST: Can not request blocks with `start_slot` greater than head block slot
        start_slot = 2

        def get_block_by_hash_tree_root(root):
            return head_block

        monkeypatch.setattr(
            bob.chain, "get_block_by_hash_tree_root", get_block_by_hash_tree_root
        )

        count = 1
        step = 1
        with pytest.raises(RequestFailure):
            await alice.request_beacon_blocks(
                peer_id=bob.peer_id,
                head_block_root=request_head_block_root,
                start_slot=start_slot,
                count=count,
                step=step,
            )

        # TEST: Can not request fork chain blocks with `start_slot`
        # lower than peer's latest finalized slot
        start_slot = head_slot
        state_machine = bob.chain.get_state_machine()
        old_state = bob.chain.get_head_state()
        new_checkpoint = old_state.finalized_checkpoint.copy(
            epoch=old_state.finalized_checkpoint.epoch + 1
        )

        def get_canonical_block_by_slot(slot):
            raise BlockNotFound

        monkeypatch.setattr(
            bob.chain, "get_canonical_block_by_slot", get_canonical_block_by_slot
        )

        def get_state_machine(at_slot=None):
            class MockStateMachine:
                state = old_state.copy(finalized_checkpoint=new_checkpoint)
                config = state_machine.config

            return MockStateMachine()

        def get_head_state():
            return old_state.copy(finalized_checkpoint=new_checkpoint)

        monkeypatch.setattr(bob.chain, "get_state_machine", get_state_machine)
        monkeypatch.setattr(bob.chain, "get_head_state", get_head_state)

        with pytest.raises(RequestFailure):
            await alice.request_beacon_blocks(
                peer_id=bob.peer_id,
                head_block_root=request_head_block_root,
                start_slot=start_slot,
                count=count,
                step=step,
            )


@pytest.mark.parametrize(
    "fork_chain_block_slots, slot_of_requested_blocks, expected_block_slots",
    (
        (range(10), [1, 4], [1, 4]),
        ([0, 2, 3, 7, 8], list(range(1, 9, 2)), [3, 7]),
        ([0, 2, 5], list(range(1, 6)), [2, 5]),
        ([0, 4, 5], [2, 3], []),
    ),
)
@pytest.mark.asyncio
async def test_get_blocks_from_fork_chain_by_root(
    monkeypatch, fork_chain_block_slots, slot_of_requested_blocks, expected_block_slots
):
    node = NodeFactory()

    mock_block = BeaconBlock(
        slot=0,
        parent_root=ZERO_HASH32,
        state_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(),
    )

    # Mock up fork chain block database
    fork_chain_blocks = []
    for slot in fork_chain_block_slots:
        if len(fork_chain_blocks) == 0:
            fork_chain_blocks.append(mock_block.copy(slot=slot))
        else:
            fork_chain_blocks.append(
                mock_block.copy(
                    slot=slot, parent_root=fork_chain_blocks[-1].signing_root
                )
            )
    mock_root_to_block_db = {block.signing_root: block for block in fork_chain_blocks}

    def get_block_by_root(root):
        if root in mock_root_to_block_db:
            return mock_root_to_block_db[root]
        else:
            raise BlockNotFound

    monkeypatch.setattr(node.chain, "get_block_by_root", get_block_by_root)

    requested_blocks = node._get_blocks_from_fork_chain_by_root(
        start_slot=slot_of_requested_blocks[0],
        peer_head_block=fork_chain_blocks[-1],
        slot_of_requested_blocks=slot_of_requested_blocks,
    )

    expected_blocks = [
        block for block in fork_chain_blocks if block.slot in expected_block_slots
    ]
    assert len(requested_blocks) == len(expected_blocks)
    assert set(requested_blocks) == set(expected_blocks)


@pytest.mark.asyncio
async def test_request_beacon_blocks_on_nonexist_chain(monkeypatch):
    async with ConnectionPairFactory() as (alice, bob):

        request_head_block_root = b"\x56" * 32

        def get_block_by_hash_tree_root(root):
            raise BlockNotFound

        monkeypatch.setattr(
            bob.chain, "get_block_by_hash_tree_root", get_block_by_hash_tree_root
        )

        start_slot = 0
        count = 5
        step = 1
        requested_blocks = await alice.request_beacon_blocks(
            peer_id=bob.peer_id,
            head_block_root=request_head_block_root,
            start_slot=start_slot,
            count=count,
            step=step,
        )

        assert len(requested_blocks) == 0


@pytest.mark.asyncio
async def test_request_recent_beacon_blocks(monkeypatch):
    async with ConnectionPairFactory() as (alice, bob):

        # Mock up block database
        head_block = BeaconBlock(
            slot=0,
            parent_root=ZERO_HASH32,
            state_root=ZERO_HASH32,
            signature=EMPTY_SIGNATURE,
            body=BeaconBlockBody(),
        )
        blocks = [head_block.copy(slot=slot) for slot in range(5)]
        mock_root_to_block_db = {block.hash_tree_root: block for block in blocks}

        def get_block_by_hash_tree_root(root):
            validate_word(root)
            if root in mock_root_to_block_db:
                return mock_root_to_block_db[root]
            else:
                raise BlockNotFound

        monkeypatch.setattr(
            bob.chain, "get_block_by_hash_tree_root", get_block_by_hash_tree_root
        )

        requesting_block_roots = [
            blocks[0].hash_tree_root,
            b"\x12" * 32,  # Unknown block root
            blocks[1].hash_tree_root,
            b"\x23" * 32,  # Unknown block root
            blocks[3].hash_tree_root,
        ]
        requested_blocks = await alice.request_recent_beacon_blocks(
            peer_id=bob.peer_id, block_roots=requesting_block_roots
        )

        expected_blocks = [blocks[0], blocks[1], blocks[3]]
        assert len(requested_blocks) == len(expected_blocks)
        assert set(requested_blocks) == set(expected_blocks)
