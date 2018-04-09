import asyncio
import logging
import time

from eth_utils import (
    to_list,
)

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


class WindbackWorker:

    YIELDED_TIME = 0.1

    is_time_up = None
    collation_validity = None

    def __init__(self, vmc, shard_tracker, my_address):
        self.vmc = vmc
        self.shard_tracker = shard_tracker
        self.my_address = my_address

        self.is_time_up = False
        # map[collation] -> validity
        self.collation_validity = {}

    @property
    def shard_id(self):
        return self.shard_tracker.shard_id

    def propagate_invalidity(self, head_collation_hash, current_collation_hash, chain_collations):
        # Set its descendants in current chain to be invalid chain heads
        collation_idx = chain_collations.index(
            current_collation_hash
        )
        chain_descendants = chain_collations[:collation_idx]
        for collation_hash in chain_descendants:
            self.collation_validity[collation_hash] = False

    async def process_collation(self,
                                head_collation_hash,
                                current_collation_hash,
                                chain_collations):
        collation = await download_collation(current_collation_hash)
        validity = await verify_collation(collation, current_collation_hash)
        if current_collation_hash not in self.collation_validity:
            self.collation_validity[current_collation_hash] = validity
        else:
            self.collation_validity[current_collation_hash] &= validity
        if not validity:
            # TODO: should have test cases
            self.propagate_invalidity(head_collation_hash, current_collation_hash, chain_collations)

    def iterate_chain(self, head_collation_hash):
        current_collation_hash = head_collation_hash
        for _ in range(self.vmc.config['WINDBACK_LENGTH'] + 1):
            if current_collation_hash == GENESIS_COLLATION_HASH:
                return
            yield current_collation_hash
            current_collation_hash = self.vmc.get_collation_parent_hash(
                self.shard_id,
                current_collation_hash,
            )

    @to_list
    def create_chain_tasks(self, head_collation_hash):
        # collations in this chain
        chain_collations = []
        for current_collation_hash in self.iterate_chain(head_collation_hash):
            chain_collations.append(current_collation_hash)
            # Process current collation  ##################################
            # If the collation is checked before, then skip it.
            # Else, create a coroutine for it to download and verify it.
            if current_collation_hash not in self.collation_validity:
                coro = self.process_collation(
                    head_collation_hash,
                    current_collation_hash,
                    chain_collations,
                )
                task = asyncio.ensure_future(coro)
                yield task
            elif not self.collation_validity[current_collation_hash]:
                # if a collation is invalid, set its descendants in the
                # chain as invalid, and skip this chain
                self.propagate_invalidity(
                    head_collation_hash,
                    current_collation_hash,
                    chain_collations,
                )
                break

    async def wait_for_chain_tasks(self, head_collation_hash, chain_tasks):
        """
        Keep running the verifying tasks.
        The loop breaks when
          1) head collations is invalid
          2) all verifying tasks are done
        Or returns when
          3) time's up
        """
        while self.collation_validity.get(head_collation_hash, True):
            is_chain_tasks_done = all([task.done() for task in chain_tasks])
            if self.is_time_up or is_chain_tasks_done:
                break
            await asyncio.wait(chain_tasks, timeout=self.YIELDED_TIME)

    async def guess_head(self):
        """
        Perform windback process.
        Returns
            the head collation hash, if it meets the windback condition. OR
            None, if there's no qualified candidate head.
        """
        start = time.time()

        for head_header in self.shard_tracker.fetch_candidate_heads_generator():
            head_collation_hash = head_header.hash

            chain_tasks = self.create_chain_tasks(head_collation_hash)

            await self.wait_for_chain_tasks(head_collation_hash, chain_tasks)

            # Only returns when the head collation is still valid after verifying tasks are done
            is_head_collation_valid = (
                head_collation_hash in self.collation_validity and
                self.collation_validity[head_collation_hash]
            )
            if self.is_time_up or is_head_collation_valid:
                logger.debug("time elapsed=%s", time.time() - start)
                return head_collation_hash

        logger.debug("time elapsed=%s", time.time() - start)
        return None

    def run_guess_head(self):
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.guess_head())
        return result
