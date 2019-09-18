from typing import (
    cast,
    Callable,
    Iterable,
    List,
    Sequence,
)
import uuid

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth.abc import SignedTransactionAPI

from p2p.abc import SessionAPI
from p2p.service import BaseService

from trinity._utils.bloom import RollingBloom
from trinity.protocol.eth.peer import (
    ETHProxyPeer,
    ETHProxyPeerPool,
)
from trinity.protocol.eth.events import (
    TransactionsEvent,
)


class TxPool(BaseService):
    """
    The :class:`~trinity.tx_pool.pool.TxPool` class is responsible for holding and relaying
    of transactions, represented as :class:`~eth.abc.SignedTransactionAPI` among the
    connected peers.

      .. note::

        This is a minimal viable implementation that only relays transactions but doesn't actually
        hold on to them yet. It's still missing many features of a grown up transaction pool.
    """

    def __init__(self,
                 event_bus: EndpointAPI,
                 peer_pool: ETHProxyPeerPool,
                 tx_validation_fn: Callable[[SignedTransactionAPI], bool],
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self._event_bus = event_bus
        self._peer_pool = peer_pool

        if tx_validation_fn is None:
            raise ValueError('Must pass a tx validation function')

        self.tx_validation_fn = tx_validation_fn
        # The effectiveness of the filter is based on the number of peers int the peer pool.
        #
        # Assuming 25 peers:
        # - each transaction will get sent to at most 24 peers resulting in 24 entries in the BF
        # - rough estimate of 100 transactions per block
        # - 2400 BF entries per block-of-transactions
        # - we'll target rotating the bloom filter every 10 minutes -> 40 blocks
        #
        # This gives a target generation size of 24 * 100 * 40 -> 96000 (round up to 100,000)
        #
        # We want our BF to remain effective for at least 24 hours -> 1440 min -> 144 generations
        #
        # Memory size can be computed as:
        #
        # bits_per_bloom = (-1 * generation_size * log(0.1)) / (log(2) ** 2) -> 479252
        # kbytes_per_bloom = bits_per_bloom / 8 / 1024 -> 58
        # kbytes_total = max_generations * kbytes_per_bloom -> 8424
        #
        # We can expect the maximum memory footprint to be about 8.5mb for the bloom filters.
        self._bloom = RollingBloom(generation_size=100000, max_generations=144)
        self._bloom_salt = uuid.uuid4()

    # This is a rather arbitrary value, but when the sync is operating normally we never see
    # the msg queue grow past a few hundred items, so this should be a reasonable limit for
    # now.
    msg_queue_maxsize: int = 2000

    async def _run(self) -> None:
        self.logger.info("Running Tx Pool")

        async for event in self.wait_iter(self._event_bus.stream(TransactionsEvent)):
            txs = cast(List[SignedTransactionAPI], event.msg)
            await self._handle_tx(event.session, txs)

    async def _handle_tx(self, sender: SessionAPI, txs: Sequence[SignedTransactionAPI]) -> None:

        self.logger.debug('Received %d transactions from %s', len(txs), sender)

        self._add_txs_to_bloom(sender, txs)

        for receiving_peer in await self._peer_pool.get_peers():

            if receiving_peer.session == sender:
                continue

            filtered_tx = self._filter_tx_for_peer(receiving_peer, txs)
            if len(filtered_tx) == 0:
                continue

            self.logger.debug2(
                'Sending %d transactions to %s',
                len(filtered_tx),
                receiving_peer,
            )
            receiving_peer.sub_proto.send_transactions(filtered_tx)
            self._add_txs_to_bloom(receiving_peer.session, filtered_tx)

    def _filter_tx_for_peer(
            self,
            peer: ETHProxyPeer,
            txs: Sequence[SignedTransactionAPI]) -> List[SignedTransactionAPI]:

        return [
            val for val in txs
            if self._construct_bloom_entry(peer.session, val) not in self._bloom
            # TODO: we need to keep track of invalid txs and eventually blacklist nodes
            if self.tx_validation_fn(val)
        ]

    def _construct_bloom_entry(self, session: SessionAPI, tx: SignedTransactionAPI) -> bytes:
        return b':'.join((
            session.id.bytes,
            tx.hash,
            self._bloom_salt.bytes,
        ))

    def _add_txs_to_bloom(self,
                          session: SessionAPI,
                          txs: Iterable[SignedTransactionAPI]) -> None:
        for val in txs:
            key = self._construct_bloom_entry(session, val)
            self._bloom.add(key)

    async def do_cleanup(self) -> None:
        self.logger.info("Stopping Tx Pool...")
