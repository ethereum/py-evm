import asyncio
import collections
from typing import (
    Any,
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
)

from evm.rlp.headers import (
    CollationHeader,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    to_canonical_address,
)
from eth_keys import (
    datatypes,
)

from p2p.service import (
    BaseService,
)
from p2p.cancel_token import (
    CancelToken,
)

from web3 import (
    Web3,
)

from sharding.handler.smc_handler import (
    SMCHandler,
)
from sharding.handler.log_handler import (
    LogHandler,
)
from sharding.handler.shard_tracker import (
    ShardTracker,
)


ShardSubscription = collections.namedtuple("ShardSubscription", [
    "shard_id",
    "added_header_queue",
])

SubscriptionsDictType = DefaultDict[int, List[ShardSubscription]]


class SMCService(BaseService):
    polling_interval = 1

    def __init__(self,
                 w3: Web3,
                 sharding_config: Dict[str, Any],
                 smc_address: Address,
                 private_key: Optional[datatypes.PrivateKey]=None,
                 token: CancelToken=None) -> None:
        super().__init__(token)

        self.w3 = w3
        self.sharding_config = sharding_config
        self.smc_address = smc_address
        self.private_key = private_key

        SMCFactory = SMCHandler.factory(web3=w3)
        self._smc_handler = SMCFactory(
            self.smc_address,
            config=self.sharding_config,
            private_key=private_key,
        )

        self._log_handler = LogHandler(self.w3, self.sharding_config["PERIOD_LENGTH"])

        self._latest_complete_period = -1  # not even period 0 is complete yet

        self._shard_trackers: Dict[int, ShardTracker] = {}
        self._subscriptions: SubscriptionsDictType = collections.defaultdict(list)

        self._processed_header_hashes: Set[Hash32] = set()

    @property
    def add_header_gas_price(self) -> int:
        return 11 * 1000 * 1000 * 1000

    def subscribe(self, shard_id: int) -> ShardSubscription:
        if shard_id not in self._shard_trackers:
            if len(self._subscriptions[shard_id]) > 0:
                raise Exception("Invariant: No shard tracker => no subscribers")

            self.logger.info("Start watching shard %d", shard_id)
            shard_tracker = ShardTracker(
                self.sharding_config,
                shard_id,
                self._log_handler,
                self.smc_address,
            )
            self._shard_trackers[shard_id] = shard_tracker
        else:
            if len(self._subscriptions[shard_id]) == 0:
                raise Exception("Invariant: Shard tracker => subscribers")

        subscription = ShardSubscription(
            shard_id=shard_id,
            added_header_queue=asyncio.Queue(),
        )
        self._subscriptions[shard_id].append(subscription)
        return subscription

    def unsubscribe(self, subscription: ShardSubscription) -> None:
        self._subscriptions[subscription.shard_id].remove(subscription)
        if len(self._subscriptions[subscription.shard_id]) == 0:
            self.logger.info("Stop watching shard %d", subscription.shard_id)
            self._shard_trackers.pop(subscription.shard_id)

    async def _run(self) -> None:
        while True:
            await self._check_logs()
            await self.wait(asyncio.sleep(self.polling_interval))

    async def _check_logs(self) -> None:
        for shard_id, shard_tracker in self._shard_trackers.items():
            added_header_logs = shard_tracker.get_add_header_logs(
                from_period=self._latest_complete_period + 1
            )

            for log in added_header_logs:
                proposer = to_canonical_address(
                    self._smc_handler.get_collation_proposer(log.shard_id, log.period)
                )
                header = CollationHeader(
                    shard_id=log.shard_id,
                    period=log.period,
                    chunk_root=log.chunk_root,
                    proposer_address=proposer,
                )

                if header.hash in self._processed_header_hashes:
                    continue

                self.logger.debug("Got AddHeader log for header %s", header)
                self._processed_header_hashes.add(header.hash)
                for subscription in self._subscriptions[shard_id]:
                    await subscription.added_header_queue.put(header)

        self._latest_complete_period = self.current_period - 1

    async def _cleanup(self) -> None:
        pass

    def add_header(self, shard_id: int, chunk_root: bytes) -> None:
        if self.private_key is None:
            raise ValueError("No private key has been configured")

        address = self.private_key.public_key.to_canonical_address()
        header = CollationHeader(
            shard_id=shard_id,
            period=self.current_period,
            chunk_root=chunk_root,
            proposer_address=address,
        )

        tx_hash = self._smc_handler.add_header(
            period=header.period,
            shard_id=header.shard_id,
            chunk_root=header.chunk_root,
            private_key=self.private_key,
            gas_price=self.add_header_gas_price,
        )
        self.logger.info("Sent tx with hash %s to add header %s", tx_hash, header)

    @property
    def current_period(self) -> int:
        return self.w3.eth.blockNumber // self.sharding_config["PERIOD_LENGTH"]
