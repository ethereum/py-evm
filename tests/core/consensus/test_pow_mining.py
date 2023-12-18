import random
import threading
import time

import pytest

from eth.chains.base import (
    MiningChain,
)
from eth.chains.mainnet import (
    MINING_MAINNET_VMS,
)
from eth.consensus.pow import (
    EPOCH_LENGTH,
    check_pow,
    get_cache,
)
from eth.tools.builder.chain import (
    genesis,
)
from eth.tools.mining import (
    POWMiningMixin,
)

TEST_NUM_CACHES = 3


def _concurrently_run_to_completion(target, concurrency):
    threads = [threading.Thread(target=target) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


@pytest.mark.skip(reason="This test takes too long to run + POW not prioritized")
def test_cache_turnover():
    expected = {}
    for block_num in range(0, EPOCH_LENGTH * TEST_NUM_CACHES):
        c = get_cache(block_num)
        expected[block_num] = c

    def lookup_random_caches():
        # the number of iterations should be enough to fill and
        # rotate the cache, while different threads poke at it
        for _ in range(TEST_NUM_CACHES):
            cache_id = random.randint(0, TEST_NUM_CACHES - 1)
            block_num = cache_id * EPOCH_LENGTH
            c = get_cache(block_num)
            assert c == expected[block_num]
            time.sleep(0.0005)

    # need a few running threads to poke the cache at the same time
    _concurrently_run_to_completion(lookup_random_caches, 3)


@pytest.mark.skip(reason="This test takes too long to run + POW not prioritized")
def test_pow_across_epochs(ropsten_epoch_headers):
    def check():
        header = random.choice(ropsten_epoch_headers)
        check_pow(
            header.block_number,
            header.mining_hash,
            header.mix_hash,
            header.nonce,
            header.difficulty,
        )

    # run a few more threads than the maximum stored in the cache,
    # to exercise the path of cache replacement in threaded context
    _concurrently_run_to_completion(check, 2)


@pytest.mark.parametrize(
    "base_vm_class",
    MINING_MAINNET_VMS,
)
def test_mining_tools_proof_of_work_mining(base_vm_class):
    vm_class = type(base_vm_class.__name__, (POWMiningMixin, base_vm_class), {})

    class ChainClass(MiningChain):
        vm_configuration = ((0, vm_class),)

    chain = genesis(ChainClass)

    block = chain.mine_block(difficulty=3)
    check_pow(
        block.number,
        block.header.mining_hash,
        block.header.mix_hash,
        block.header.nonce,
        block.header.difficulty,
    )
