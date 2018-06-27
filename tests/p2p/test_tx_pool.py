import asyncio
import pytest
import random

from p2p.peer import (
    ETHPeer,
)
from p2p.eth import (
    Transactions
)
from evm.rlp.transactions import (
    BaseTransactionFields
)

from trinity.tx_pool.pool import (
    TxPool,
)

from tests.p2p.peer_helpers import (
    get_directly_linked_peers,
    MockPeerPoolWithConnectedPeers,
)

# TODO: Move this file into the trinity tests (Requires refactor of peer_helpers)


class TxsRecorder():
    def __init__(self):
        self.recorded_tx = []
        self.send_count = 0

    def send_txs(self, txs):
        self.recorded_tx.extend(txs)
        self.send_count = self.send_count + 1

async def bootstrap_test_setup(monkeypatch, request, event_loop):
    peer1, peer2 = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=ETHPeer,
        peer2_class=ETHPeer,
    )

    # We intercept sub_proto.send_transactions to record detailed information
    # about which peer received what and was invoked how often.
    peer1_txs_recorder = create_tx_recorder(monkeypatch, peer1)
    peer2_txs_recorder = create_tx_recorder(monkeypatch, peer2)

    pool = TxPool(MockPeerPoolWithConnectedPeers([peer1, peer2]))

    asyncio.ensure_future(pool.run())

    def finalizer():
        event_loop.run_until_complete(pool.cancel())
    request.addfinalizer(finalizer)

    return peer1, peer1_txs_recorder, peer2, peer2_txs_recorder, pool

@pytest.mark.asyncio
async def test_tx_propagation(monkeypatch, request, event_loop):
    peer1, peer1_txs_recorder, peer2, peer2_txs_recorder, pool = await bootstrap_test_setup(
        monkeypatch,
        request,
        event_loop
    )

    txs_broadcasted_by_peer1 = [create_random_tx()]

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
    txs_broadcasted_by_peer2 = [create_random_tx(), txs_broadcasted_by_peer1[0]]
    await pool._handle_tx(peer2, txs_broadcasted_by_peer2)

    # Check that Peer1 receives only the one tx that it didn't know about
    assert len(peer1_txs_recorder.recorded_tx) == 1
    assert peer1_txs_recorder.recorded_tx[0].hash == txs_broadcasted_by_peer2[0].hash
    assert peer1_txs_recorder.send_count == 1


@pytest.mark.asyncio
async def test_tx_sending(request, event_loop):
    # This test covers the communication end to end whereas the previous
    # focusses on the rules of the transaction pool on when to send tx to whom
    peer1, peer2 = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=ETHPeer,
        peer2_class=ETHPeer,
    )

    peer2_subscriber = asyncio.Queue()
    peer2.add_subscriber(peer2_subscriber)

    pool = TxPool(MockPeerPoolWithConnectedPeers([peer1, peer2]))

    asyncio.ensure_future(pool.run())

    def finalizer():
        event_loop.run_until_complete(pool.cancel())
    request.addfinalizer(finalizer)

    txs = [create_random_tx()]

    peer1.sub_proto.send_transactions(txs)

    # Ensure that peer2 gets the transactions
    peer, cmd, msg = await asyncio.wait_for(
        peer2_subscriber.get(),
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


def create_random_tx():
    return BaseTransactionFields(
        nonce=0,
        gas_price=1,
        gas=21000,
        data=b'',
        to=b'',
        value=random.randint(0, 1000),
        r=random.randint(0, 1000),
        s=random.randint(0, 1000),
        v=random.randint(0, 1000)
    )
