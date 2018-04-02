import asyncio
from collections import (
    defaultdict,
)
import logging
import time

from evm.vm.forks.sharding.constants import (
    GENESIS_COLLATION_HASH,
)
from evm.vm.forks.sharding.shard_tracker import (
    NoCandidateHead,
)


NUM_RESERVED_BLOCKS = 5
SIMULATED_COLLATION_DOWNLOADING_TIME = 2
SIMULATED_COLLATION_VERIFICATION_TIME = 0.01


logger = logging.getLogger("evm.chain.sharding.guess_head_state_manager")


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


async def fetch_and_verify_collation(collation_hash):
    """Fetch the collation body and verify the collation

    :return: returns the collation's validity
    """
    collation = await download_collation(collation_hash)
    return await verify_collation(collation, collation_hash)


def clean_done_task(tasks):
    return [task for task in tasks if not task.done()]


class GuessHeadStateManager:

    TIME_ONE_STEP = 0.1

    logger = logging.getLogger("evm.chain.sharding.GuessHeadStateManager")

    is_time_up = None
    last_period_fetching_candidate_head = None

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
        self.last_period_fetching_candidate_head = 0

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

    async def verify_collation(self, head_collation_hash, collation_hash):
        coroutine = fetch_and_verify_collation(
            collation_hash,
        )
        task = asyncio.ensure_future(coroutine)
        collation_validity = await asyncio.wait_for(task, None)
        self.collation_validity_cache[collation_hash] = collation_validity
        if not collation_validity:
            self.chain_validity[head_collation_hash] = False

    def fetch_candidate_head_hash(self):
        head_collation_hash = None
        try:
            head_collation_dict = self.shard_tracker.fetch_candidate_head()
            head_collation_hash = head_collation_dict['header'].hash
        except NoCandidateHead:
            self.logger.debug("No candidate head available, `guess_head` stops")
        self.last_period_fetching_candidate_head = self.get_current_period()
        return head_collation_hash

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

    async def guess_head(self):
        '''
        Perform windback process.
        returns None if there is no candidate head available in this period
        '''
        start = time.time()

        head_collation_hash = current_collation_hash = None
        self.unfinished_verifying_tasks = []
        while True:
            # discard old logs if we're in the new period
            if self.get_current_period() > self.last_period_fetching_candidate_head:
                self.shard_tracker.clean_logs()
            head_collation_hash = self.fetch_candidate_head_hash()
            if head_collation_hash is None:
                break
            current_collation_hash = head_collation_hash
            for _ in range(self.vmc.config['WINDBACK_LENGTH'] + 1):
                # if time is up
                if self.is_time_up:
                    return head_collation_hash
                if current_collation_hash == GENESIS_COLLATION_HASH:
                    break
                # process current collation
                # if the collation is checked before, just skip it
                if current_collation_hash not in self.collation_validity_cache:
                    coro = self.verify_collation(
                        head_collation_hash,
                        current_collation_hash,
                    )
                    task = asyncio.ensure_future(coro)
                    asyncio.wait(task, timeout=self.TIME_ONE_STEP)
                    self.set_collation_task(head_collation_hash, current_collation_hash, task)
                else:
                    # if the collation is invalid, set its head's chain validity False
                    self.chain_validity[head_collation_hash] &= self.collation_validity_cache[
                        current_collation_hash
                    ]

                current_collation_hash = self.vmc.get_collation_parent_hash(
                    self.get_shard_id(),
                    current_collation_hash,
                )

                # clean up the finished tasks, yield CPU to tasks
                if len(self.unfinished_verifying_tasks) != 0:
                    await asyncio.wait(self.unfinished_verifying_tasks, timeout=self.TIME_ONE_STEP)
                    self.unfinished_verifying_tasks = clean_done_task(
                        self.unfinished_verifying_tasks
                    )
                # yield the CPU to other coroutine
                await asyncio.sleep(self.TIME_ONE_STEP)

            # when `WINDBACK_LENGTH` or GENESIS_COLLATION is reached
            while self.chain_validity[head_collation_hash]:
                # if time is up
                if self.is_time_up:
                    return head_collation_hash
                candidate_chain_tasks = self.get_chain_tasks(head_collation_hash)
                is_chain_tasks_done = all([task.done() for task in candidate_chain_tasks])
                if is_chain_tasks_done:
                    break
                await asyncio.wait(candidate_chain_tasks, timeout=self.TIME_ONE_STEP)
            # if we break from `while`, either the chain is done or chain is invalid
            # Case 1:
            #   if the chain_validity is True, it means chain_tasks are done and
            #   chain_validity is still True, return
            # Case 2:
            #   chain_validity is False, just change to other candidate head
            if self.chain_validity[head_collation_hash]:
                break
        logger.debug("time elapsed=%s", time.time() - start)
        return head_collation_hash

    def run_guess_head(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.guess_head())
        return result
