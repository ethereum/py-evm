import asyncio
from collections import (
    defaultdict,
)
import copy
import logging
import time

from evm.vm.forks.sharding.constants import (
    GENESIS_COLLATION_HASH,
)


NUM_RESERVED_BLOCKS = 5
SIMULATED_COLLATION_DOWNLOADING_TIME = 2
SIMULATED_COLLATION_VERIFICATION_TIME = 0.01


logger = logging.getLogger("evm.chain.sharding.windback_worker")


async def download_collation(collation_hash):
    # TODO: need to implemented after p2p part is done
    logger.debug("Start downloading collation %s", collation_hash)
    await asyncio.sleep(SIMULATED_COLLATION_DOWNLOADING_TIME)
    logger.debug("Finished downloading collation %s", collation_hash)
    collation = collation_hash
    return collation


async def verify_collation(collation, collation_hash):
    # TODO: to be implemented
    logger.debug("Verifying collation %s", collation_hash)
    await asyncio.sleep(SIMULATED_COLLATION_VERIFICATION_TIME)
    # data = get_from_p2p_network(collation_hash.data_root)
    # chunks = DATA_SIZE // 32
    # mtree = [0] * chunks + [data[chunks*32: chunks*32+32] for i in range(chunks)]
    # for i in range(chunks-1, 0, -1):
    #     mtree[i] = sha3(mtree[i*2] + mtree[i*2+1])
    # assert mtree[i] == collation.data_root
    return True


def clean_done_tasks(tasks):
    return [task for task in tasks if not task.done()]


class WindbackWorker:

    YIELDED_TIME = 0.1

    is_time_up = None
    latest_fetching_period = None

    collation_validity_cache = None
    chain_validity = None

    unfinished_verifying_tasks = None
    collation_verifying_task = None
    chain_collations = None

    def __init__(self, vmc, shard_tracker, my_address):
        self.vmc = vmc
        self.shard_tracker = shard_tracker
        self.my_address = my_address

        self.is_time_up = False
        self.latest_fetching_period = 0

        # map[collation] -> validity
        self.collation_validity_cache = {}
        # map[chain_head] -> validity
        # this should be able to be updated by the collations' validity
        self.chain_validity = defaultdict(lambda: True)

        # current tasks
        self.unfinished_verifying_tasks = []
        # map[collation_hash] -> task
        self.collation_verifying_task = {}
        # map[chain_head] -> list of collations
        # the collations in the chain
        self.chain_collations = defaultdict(list)

    def get_shard_id(self):
        return self.shard_tracker.shard_id

    # time related

    def get_current_period(self):
        return self.vmc.web3.eth.blockNumber // self.vmc.config['PERIOD_LENGTH']

    # guess_head process related

    async def process_collation(self, head_collation_hash, current_collation_hash, descendants):
        collation = await download_collation(current_collation_hash)
        collation_validity = await verify_collation(collation, current_collation_hash)
        self.collation_validity_cache[current_collation_hash] = collation_validity
        if not collation_validity:
            # Set its descendants in current chain to be invalid chain heads
            self.chain_validity[current_collation_hash] = False
            for collation_hash in descendants:
                self.chain_validity[collation_hash] = False

    def set_collation_task(self, head_collation_hash, current_collation_hash, task):
        self.unfinished_verifying_tasks.append(task)
        self.collation_verifying_task[current_collation_hash] = task
        self.chain_collations[head_collation_hash].append(current_collation_hash)

    def get_chain_tasks(self, head_collation_hash):
        # ignore tasks that are done
        return [
            self.collation_verifying_task[collation_hash]
            for collation_hash in self.chain_collations[head_collation_hash]
        ]

    def iterate_ancestors(self, head_collation_hash):
        current_collation_hash = head_collation_hash
        for _ in range(self.vmc.config['WINDBACK_LENGTH'] + 1):
            yield current_collation_hash
            current_collation_hash = self.vmc.get_collation_parent_hash(
                self.get_shard_id(),
                current_collation_hash,
            )

    async def guess_head(self):
        '''
        Perform windback process.
        Returns
            the head collation hash, if it meets the windback condition. OR
            None, if there's no qualified candidate head.
        '''
        start = time.time()

        head_collation_hash = current_collation_hash = None
        self.unfinished_verifying_tasks = []
        candidate_heads = self.shard_tracker.fetch_candidate_heads_generator()
        while True:
            try:
                head_header = next(candidate_heads)
            except StopIteration:
                return None
            head_collation_hash = head_header.hash
            if not self.chain_validity[head_collation_hash]:
                continue
            for current_collation_hash in self.iterate_ancestors(head_collation_hash):
                # if time is up
                if self.is_time_up:
                    return head_collation_hash
                if current_collation_hash == GENESIS_COLLATION_HASH:
                    break

                # if a collation is an invalid head, set its descendants in the
                # chain as invalid heads, and skip this chain
                is_chain_of_current_collation_invalid = (
                    (not self.chain_validity[current_collation_hash]) or
                    (not self.collation_validity_cache.get(current_collation_hash, True))
                )
                if is_chain_of_current_collation_invalid:
                    self.chain_validity[current_collation_hash] = False
                    for collation_hash in self.chain_collations[head_collation_hash]:
                        self.chain_validity[collation_hash] = False
                    break
                # process current collation  ##################################
                # if the collation is checked before, then skip it
                if current_collation_hash not in self.collation_validity_cache:
                    descendants = copy.deepcopy(
                        self.chain_collations[head_collation_hash]
                    )
                    coro = self.process_collation(
                        head_collation_hash,
                        current_collation_hash,
                        descendants,
                    )
                    task = asyncio.ensure_future(coro)
                    self.set_collation_task(head_collation_hash, current_collation_hash, task)

            # when `WINDBACK_LENGTH` or GENESIS_COLLATION is reached
            while self.chain_validity[head_collation_hash]:
                # if time is up
                if self.is_time_up:
                    return head_collation_hash
                candidate_chain_tasks = self.get_chain_tasks(head_collation_hash)
                is_chain_tasks_done = all([task.done() for task in candidate_chain_tasks])
                if is_chain_tasks_done:
                    break
                await asyncio.wait(candidate_chain_tasks, timeout=self.YIELDED_TIME)
            # if we break from `while`, either the chain is done or chain is invalid
            # Case 1:
            #   if the chain_validity is True, it means chain_tasks are done and
            #   chain_validity is still True, return
            # Case 2:
            #   chain_validity is False, just change to other candidate head
            if self.chain_validity[head_collation_hash]:
                return head_collation_hash
        logger.debug("time elapsed=%s", time.time() - start)
        return head_collation_hash

    def run_guess_head(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.guess_head())
        return result
