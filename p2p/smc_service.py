import asyncio
import collections
from typing import (
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
)

from evm.rlp.headers import (
    CollationHeader,
)

from evm.exceptions import (
    ValidationError,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    to_checksum_address,
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
from sharding.contracts.utils.config import (
    get_sharding_config,
)


class SMCService(BaseService):
    w3: Web3 = None
    config = get_sharding_config()

    def __init__(self,
                 smc_address: Address,
                 shard_ids: List[int]=None,
                 private_key: Optional[datatypes.PrivateKey]=None,
                 token: CancelToken=None) -> None:
        if self.w3 is None:
            raise ValueError("Web3 connection has not been configured yet")

        super().__init__(token)
        self.smc_address = smc_address
        self.private_key = private_key

        self._smc_handler = self.w3.eth.contract(
            address=self.smc_address,
            ContractFactoryClass=SMCHandler,
            config=self.config,
        )
        self._log_handler = LogHandler(self.w3, self.config["PERIOD_LENGTH"])

        self._shard_trackers: Dict[int, ShardTracker] = {}
        self._added_header_queues: DefaultDict[
            int,
            List[asyncio.Queue[CollationHeader]]
        ] = collections.defaultdict(list)
        for shard_id in shard_ids or []:
            self.start_watching_shard(shard_id)

        self._processed_header_hashes: Set[Hash32] = set()

    @property
    def add_header_gas_price(self) -> int:
        return 11 * 1000 * 1000 * 1000

    def start_watching_shard(self, shard_id: int) -> asyncio.Queue[CollationHeader]:
        if shard_id in self._shard_trackers:
            raise ValueError("Already watching shard {}".format(shard_id))

        self.logger.debug("Start watching shard {}".format(shard_id))
        shard_tracker = ShardTracker(self.config, shard_id, self._log_handler, self.smc_address)
        queue: asyncio.Queue[CollationHeader] = asyncio.Queue()
        self._shard_trackers[shard_id] = shard_tracker
        self._added_header_queues[shard_id].append(queue)
        return queue

    def stop_watching_shard(self, shard_id: int) -> None:
        if shard_id not in self._shard_trackers:
            raise ValueError("Not watching shard {}".format(shard_id))

        self.logger.debug("Stop watching shard {}".format(shard_id))
        self._shard_trackers.pop(shard_id)
        self._added_header_queues.pop(shard_id)

    def watching_shard(self, shard_id: int) -> bool:
        return shard_id in self._shard_trackers

    async def _run(self) -> None:
        while True:
            for shard_id, shard_tracker in self._shard_trackers.items():
                added_header_logs = await shard_tracker.get_add_header_logs()
                for log in added_header_logs:
                    proposer = self._smc_handler.get_collation_proposer(log.period, log.shard_id)
                    header = CollationHeader(
                        shard_id=log.shard_id,
                        period=log.period,
                        chunk_root=log.chunk_root,
                        propser_address=proposer,
                    )

                    if header.hash in self._processed_header_hashes:
                        continue

                    self.logger.debug("Got AddHeader log for header %s", header)
                    self._processed_header_hashes.add(header.hash)
                    for added_header_queue in self._added_header_queues[shard_id]:
                        await added_header_queue.put(header)

    def add_header(self, collation_header: CollationHeader) -> None:
        if self.private_key is None:
            raise ValueError("No private key has been configured")
        address = self.private_key.public_key.to_canonical_address
        if collation_header.proposer_address != address:
            raise ValidationError(
                "Collation proposer address {} is different from our address {}".format(
                    to_checksum_address(collation_header.proposer_address),
                    to_checksum_address(address),
                )
            )

        self.logger.info("Sending tx to add header %s", collation_header)
        self._smc_handler.add_header(
            period=collation_header.period,
            shard_id=collation_header.shard_id,
            chunk_root=collation_header.chunk_root,
            private_key=self.private_key,
            gas_price=self.add_header_gas_price,
        )
