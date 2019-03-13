import pytest
import random
import threading
import time

from eth.chains.base import MiningChain
from eth.chains.mainnet import MAINNET_VMS
from eth.consensus.pow import (
    CACHE_MAX_ITEMS,
    EPOCH_LENGTH,
    check_pow,
    get_cache,
)
from eth.tools.mining import POWMiningMixin
from eth.tools.builder.chain import (
    genesis,
)


def _concurrently_run_to_completion(target, concurrency):
    threads = [threading.Thread(target=target) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_cache_turnover():
    expected = {}
    num_caches = CACHE_MAX_ITEMS + 2
    for block_num in range(0, EPOCH_LENGTH * num_caches):
        c = get_cache(block_num)
        expected[block_num] = c

    def lookup_random_caches():
        for _ in range(50):
            cache_id = random.randint(0, num_caches - 1)
            block_num = cache_id * EPOCH_LENGTH
            c = get_cache(block_num)
            assert c == expected[block_num]
            time.sleep(0.0005)

    _concurrently_run_to_completion(lookup_random_caches, 5)


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

    _concurrently_run_to_completion(check, 100)


@pytest.mark.parametrize(
    'base_vm_class',
    MAINNET_VMS,
)
def test_mining_tools_proof_of_work_mining(base_vm_class):
    vm_class = type(base_vm_class.__name__, (POWMiningMixin, base_vm_class), {})

    class ChainClass(MiningChain):
        vm_configuration = (
            (0, vm_class),
        )

    chain = genesis(ChainClass)

    block = chain.mine_block()
    check_pow(
        block.number,
        block.header.mining_hash,
        block.header.mix_hash,
        block.header.nonce,
        block.header.difficulty,
    )
