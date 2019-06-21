from typing import (
    cast,
    Callable,
    Iterable,
    List,
)
import uuid

from bloom_filter import (
    BloomFilter
)

from cancel_token import CancelToken

from eth.rlp.transactions import (
    BaseTransactionFields
)

from p2p.kademlia import (
    Node,
)
from p2p.service import (
    BaseService
)

from trinity.endpoint import TrinityEventBusEndpoint
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
    of transactions, represented as :class:`~eth.rlp.transactions.BaseTransaction` among the
    connected peers.

      .. note::

        This is a minimal viable implementation that only relays transactions but doesn't actually
        hold on to them yet. It's still missing many features of a grown up transaction pool.
    """

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 peer_pool: ETHProxyPeerPool,
                 tx_validation_fn: Callable[[BaseTransactionFields], bool],
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self._event_bus = event_bus
        self._peer_pool = peer_pool

        if tx_validation_fn is None:
            raise ValueError('Must pass a tx validation function')

        self.tx_validation_fn = tx_validation_fn
        # 1m should give us 9000 blocks before that filter becomes less reliable
        # It should take up about 1mb of memory
        self._bloom = BloomFilter(max_elements=1000000)
        self._bloom_salt = str(uuid.uuid4())

    # This is a rather arbitrary value, but when the sync is operating normally we never see
    # the msg queue grow past a few hundred items, so this should be a reasonable limit for
    # now.
    msg_queue_maxsize: int = 2000

    async def _run(self) -> None:
        self.logger.info("Running Tx Pool")

        async for event in self.wait_iter(self._event_bus.stream(TransactionsEvent)):
            txs = cast(List[BaseTransactionFields], event.msg)
            await self._handle_tx(event.remote, txs)

    async def _handle_tx(self, sender: Node, txs: List[BaseTransactionFields]) -> None:

        self.logger.debug('Received %d transactions from %s', len(txs), sender)

        self._add_txs_to_bloom(sender, txs)

        for receiving_peer in await self._peer_pool.get_peers():

            if receiving_peer.remote is sender:
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
            self._add_txs_to_bloom(receiving_peer.remote, filtered_tx)

    def _filter_tx_for_peer(
            self,
            peer: ETHProxyPeer,
            txs: List[BaseTransactionFields]) -> List[BaseTransactionFields]:

        return [
            val for val in txs
            if self._construct_bloom_entry(peer.remote, val) not in self._bloom
            # TODO: we need to keep track of invalid txs and eventually blacklist nodes
            if self.tx_validation_fn(val)
        ]

    def _construct_bloom_entry(self, remote: Node, tx: BaseTransactionFields) -> bytes:
        return f"{repr(remote)}-{tx.hash}-{self._bloom_salt}".encode()

    def _add_txs_to_bloom(self, remote: Node, txs: Iterable[BaseTransactionFields]) -> None:
        for val in txs:
            self._bloom.add(self._construct_bloom_entry(remote, val))

    async def do_cleanup(self) -> None:
        self.logger.info("Stopping Tx Pool...")
