import asyncio
import pytest
import uuid

from eth.tools.logging import TraceLogger
from eth.utils.address import (
    force_bytes_to_address
)

from p2p.peer import PeerSubscriber
from p2p.protocol import Command

from trinity.plugins.builtin.tx_pool.pool import (
    TxPool,
)
from trinity.plugins.builtin.tx_pool.validators import (
    DefaultTransactionValidator
)
from trinity.protocol.eth.commands import (
    Transactions
)

from tests.conftest import (
    funded_address_private_key
)
from tests.trinity.core.peer_helpers import (
    get_directly_linked_peers,
    MockPeerPoolWithConnectedPeers,
)


class SamplePeerSubscriber(PeerSubscriber):
    logger = TraceLogger("")

    subscription_msg_types = {Command}

    @property
    def msg_queue_maxsize(self) -> int:
        return 100


class TxsRecorder():
    def __init__(self):
        self.recorded_tx = []
        self.send_count = 0

    def send_txs(self, txs):
        self.recorded_tx.extend(txs)
        self.send_count = self.send_count + 1


async def bootstrap_test_setup(monkeypatch, request, event_loop, chain, tx_validator):
    peer1, peer2 = await get_directly_linked_peers(
        request,
        event_loop,
    )

    # We intercept sub_proto.send_transactions to record detailed information
    # about which peer received what and was invoked how often.
    peer1_txs_recorder = create_tx_recorder(monkeypatch, peer1)
    peer2_txs_recorder = create_tx_recorder(monkeypatch, peer2)

    pool = TxPool(
        MockPeerPoolWithConnectedPeers([peer1, peer2]),
        tx_validator
    )

    asyncio.ensure_future(pool.run())

    def finalizer():
        event_loop.run_until_complete(pool.cancel())
    request.addfinalizer(finalizer)

    return peer1, peer1_txs_recorder, peer2, peer2_txs_recorder, pool


@pytest.fixture
def tx_validator(chain_with_block_validation):
    return DefaultTransactionValidator(chain_with_block_validation, 0)


@pytest.mark.asyncio
async def test_tx_propagation(monkeypatch,
                              request,
                              event_loop,
                              chain_with_block_validation,
                              tx_validator):

    peer1, peer1_txs_recorder, peer2, peer2_txs_recorder, pool = await bootstrap_test_setup(
        monkeypatch,
        request,
        event_loop,
        chain_with_block_validation,
        tx_validator
    )

    txs_broadcasted_by_peer1 = [create_random_tx(chain_with_block_validation)]

    # Peer1 sends some txs
    await pool._handle_tx(peer1, txs_broadcasted_by_peer1)

    # Check that we don't send the txs back to peer1 where they came from
    assert peer1_txs_recorder.send_count == 0

    # Check that Peer2 receives them
    assert len(peer2_txs_recorder.recorded_tx) == 1
    assert peer2_txs_recorder.recorded_tx[0].hash == txs_broadcasted_by_peer1[0].hash

    # Peer1 sends same txs again
    await pool._handle_tx(peer1, txs_broadcasted_by_peer1)

    # Check that Peer2 doesn't receive them again
    assert peer2_txs_recorder.send_count == 1

    # Peer2 sends exact same txs back
    await pool._handle_tx(peer2, txs_broadcasted_by_peer1)

    # Check that Peer1 won't get them as that is where they originally came from
    assert len(peer1_txs_recorder.recorded_tx) == 0
    # Also ensure, we don't even call send_transactions with an empty tx list
    assert peer1_txs_recorder.send_count == 0

    # Peer2 sends old + new tx
    txs_broadcasted_by_peer2 = [
        create_random_tx(chain_with_block_validation),
        txs_broadcasted_by_peer1[0]
    ]
    await pool._handle_tx(peer2, txs_broadcasted_by_peer2)

    # Check that Peer1 receives only the one tx that it didn't know about
    assert len(peer1_txs_recorder.recorded_tx) == 1
    assert peer1_txs_recorder.recorded_tx[0].hash == txs_broadcasted_by_peer2[0].hash
    assert peer1_txs_recorder.send_count == 1


@pytest.mark.asyncio
async def test_does_not_propagate_invalid_tx(monkeypatch,
                                             request,
                                             event_loop,
                                             chain_with_block_validation,
                                             tx_validator):

    peer1, peer1_txs_recorder, peer2, peer2_txs_recorder, pool = await bootstrap_test_setup(
        monkeypatch,
        request,
        event_loop,
        chain_with_block_validation,
        tx_validator
    )

    txs_broadcasted_by_peer1 = [
        create_random_tx(chain_with_block_validation, is_valid=False),
        create_random_tx(chain_with_block_validation)
    ]

    # Peer1 sends some txs
    await pool._handle_tx(peer1, txs_broadcasted_by_peer1)

    # Check that Peer2 received only the second tx which is valid
    assert len(peer2_txs_recorder.recorded_tx) == 1
    assert peer2_txs_recorder.recorded_tx[0].hash == txs_broadcasted_by_peer1[1].hash


@pytest.mark.asyncio
async def test_tx_sending(request, event_loop, chain_with_block_validation, tx_validator):
    # This test covers the communication end to end whereas the previous
    # focusses on the rules of the transaction pool on when to send tx to whom
    peer1, peer2 = await get_directly_linked_peers(
        request,
        event_loop,
    )

    peer2_subscriber = SamplePeerSubscriber()
    peer2.add_subscriber(peer2_subscriber)

    pool = TxPool(MockPeerPoolWithConnectedPeers([peer1, peer2]), tx_validator)

    asyncio.ensure_future(pool.run())

    def finalizer():
        event_loop.run_until_complete(pool.cancel())
    request.addfinalizer(finalizer)

    txs = [create_random_tx(chain_with_block_validation)]

    peer1.sub_proto.send_transactions(txs)

    # Ensure that peer2 gets the transactions
    peer, cmd, msg = await asyncio.wait_for(
        peer2_subscriber.msg_queue.get(),
        timeout=0.1,
    )

    assert peer == peer2
    assert isinstance(cmd, Transactions)
    assert msg[0].hash == txs[0].hash


def create_tx_recorder(monkeypatch, peer):
    recorder = TxsRecorder()
    monkeypatch.setattr(
        peer.sub_proto,
        'send_transactions',
        lambda txs: recorder.send_txs(txs)
    )
    return recorder


def create_random_tx(chain, is_valid=True):
    return chain.create_unsigned_transaction(
        nonce=0,
        gas_price=1,
        gas=2100000000000 if is_valid else 0,
        # For simplicity, both peers create tx with the same private key.
        # We rely on unique data to create truly unique txs
        data=uuid.uuid4().bytes,
        to=force_bytes_to_address(b'\x10\x10'),
        value=1,
    ).as_signed_transaction(funded_address_private_key())
