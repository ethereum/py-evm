import logging
import json
import re
from typing import (
    Any,
    Callable,
)

from eth.chains.base import (
    Chain,
    MiningChain,
)
from eth.db.backends.base import (
    BaseDB
)
from eth.consensus.pow import (
    mine_pow_nonce
)
from utils.chain_plumbing import (
    DB,
    get_all_chains,
)
from utils.format import (
    format_block
)
from utils.reporting import (
    DefaultStat
)

from .base_benchmark import (
    BaseBenchmark
)


def Mine(chain: MiningChain, POW_fixture: dict, num_blocks: int) -> int:
    #run
    vm = chain.get_vm()
    total_gas_used = 0

    for i in range(1, num_blocks + 1):
        # get values from fixture
        nonce = bytes.fromhex(POW_fixture[vm.fork][str(i)]["nonce"])
        mix_hash = bytes.fromhex(POW_fixture[vm.fork][str(i)]["mix_hash"])
        # mine block
        block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)
        logging.debug(format_block(block))

    total_gas_used = total_gas_used + block.header.gas_used
    logging.debug(format_block(block))

    return total_gas_used


def Import(chain: Chain, POW_fixture: dict, num_blocks: int) -> int:
    #run
    vm = chain.get_vm()
    old_block = chain.get_canonical_block_by_number(0)
    total_gas_used = 0

    for i in range(1, num_blocks + 1):
        # get values from fixture
        nonce = bytes.fromhex(POW_fixture[vm.fork][str(i)]["nonce"])
        mix_hash = bytes.fromhex(POW_fixture[vm.fork][str(i)]["mix_hash"])
        state_root = bytes.fromhex(POW_fixture[vm.fork][str(i)]["state_root"])

        # create new block
        block = chain.get_vm().generate_block_from_parent_header_and_coinbase(old_block.header, old_block.header.coinbase)
        block.header._nonce = nonce
        block.header._mix_hash = mix_hash
        block.header._state_root = state_root

        # import block then set to old_block
        block = chain.import_block(block)
        old_block = block
        total_gas_used = total_gas_used + block.header.gas_used
        logging.debug(format_block(block))

    return total_gas_used


def make_POW_fixtures(db: BaseDB, POW_file_path: str, num_blocks: int) -> None:
    POW_fixtures = {}

    for chain in get_all_chains(db):
        POW_fork = {}

        for i in range(1, num_blocks + 1):
            POW_block = {}

            block = chain.get_vm().finalize_block(chain.get_block())
            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)

            block = chain.mine_block(mix_hash=mix_hash, nonce=nonce)

            POW_block["mix_hash"] = mix_hash.hex()
            POW_block["nonce"] = nonce.hex()
            POW_block["state_root"] = block.header.state_root.hex()
            POW_fork[i] = POW_block
        POW_fixtures[chain.get_vm().fork] = POW_fork

    with open(POW_file_path, 'w') as outfile:
        json.dump(POW_fixtures, outfile, indent=4)


class EmptyBlocks(BaseBenchmark):

    def __init__(self, benchmark: Callable, db: DB, num_blocks: int, validate_POW: bool, make_POW_fixture: bool) -> None:
        self.name = re.search(r'\s(\w+)\s',
                              str(benchmark)
                              ).group(1).replace('_', ' ') + " empty blocks"
        self.benchmark = benchmark
        self.db = db
        self.num_blocks = num_blocks
        self.validate_POW = validate_POW
        self.make_POW_fixture = make_POW_fixture

        self.POW_file_path = "scripts/benchmark/fixtures/empty_blocks.json"
        self.POW_fixture = {}

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        #####  SETUP  #####
        # make the Proof of Work fixture
        if self.make_POW_fixture:
            make_POW_fixtures(self.db, self.POW_file_path, self.num_blocks)
            logging.info("CREATED FIXTURE NOT REPORTING STATS")
            total_stat = DefaultStat(total_seconds=1)
            return total_stat
        # load fixtures
        with open(self.POW_file_path, 'r') as outfile:
            self.POW_fixture = json.load(outfile)

        for chain in get_all_chains(self.db, self.validate_POW):

            #####  RUN  #####
            value = self.as_timed_result(lambda: self.benchmark(chain, self.POW_fixture, self.num_blocks))

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_seconds=value.duration
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat
