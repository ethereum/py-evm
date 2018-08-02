import logging
import json
import math
import re

from typing import (
    Callable,
    NamedTuple,
    Tuple,
    Union
)

from eth_typing import (
    Address,
)
from eth.chains.base import (
    MiningChain,
)
from eth.consensus.pow import (
    mine_pow_nonce
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.transactions import (
    BaseTransaction
)
from .base_benchmark import (
    BaseBenchmark,
)
from utils.chain_plumbing import (
    DB,
    get_all_chains,
)
from utils.address import (
    FIRST_ACCOUNT,
    SECOND_ACCOUNT,
    generate_random_address,
)
from utils.reporting import (
    DefaultStat,
)
from utils.shellart import (
    bold_yellow,
)
from utils.tx import (
    new_transaction,
)

def Existing_address(chain: MiningChain, POW_fixture: dict, num_blocks: int, make_POW_fixture: bool=False) -> Union[dict, Tuple[int, int]]:
    random_address = False
    if make_POW_fixture:
        POW_fork = mine_blocks(chain, POW_fixture, num_blocks, random_address, make_POW_fixture)
        return POW_fork
    else:
        # run nomal benchmark if not needing to generate POW
        total_gas_used, total_num_tx = mine_blocks(chain, POW_fixture, num_blocks, random_address, make_POW_fixture)
        return total_gas_used, total_num_tx


def Non_existing_address(chain: MiningChain, POW_fixture: dict, num_blocks: int, make_POW_fixture: bool=False) -> Union[dict, Tuple[int, int]]:
    random_address = True
    if make_POW_fixture:
        POW_fork = mine_blocks(chain, POW_fixture, num_blocks, random_address, make_POW_fixture)
        return POW_fork
    else:
        total_gas_used, total_num_tx = mine_blocks(chain, POW_fixture, num_blocks, random_address, make_POW_fixture)
        return total_gas_used, total_num_tx


def make_POW_fixtures(benchmark: Callable, db: DB, POW_file_path: str, num_blocks: int) -> None:
    POW_fixture = {}

    for chain in get_all_chains(db):
        POW_fork = benchmark(chain, POW_fixture, num_blocks, make_POW_fixture=True)
        POW_fixture[chain.get_vm().fork] = POW_fork

    with open(POW_file_path, 'w') as outfile:
        json.dump(POW_fixture, outfile, indent=4)


def mine_blocks(chain: MiningChain, POW_fixture: dict, num_blocks: int, random_address: bool, make_POW_fixture: bool) -> Union[dict, Tuple[int, int]]:
    total_gas_used = 0
    total_num_tx = 0
    vm = chain.get_vm()
    if make_POW_fixture:
        POW_fork = {}
        for i in range(1, num_blocks + 1):
            POW_block = {}
            block = mine_block(chain, i, random_address)
            block = chain.get_vm().finalize_block(chain.get_block())
            nonce, mix_hash = mine_pow_nonce(
                    block.number,
                    block.header.mining_hash,
                    block.header.difficulty)
            block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)
            POW_block["mix_hash"] = mix_hash.hex()
            POW_block["nonce"] = nonce.hex()
            POW_block["state_root"] = block.header.state_root.hex()
            POW_fork[i] = POW_block
        return POW_fork
    else:
        for i in range(1, num_blocks + 1):
            block = mine_block(chain, i, random_address)
            nonce = bytes.fromhex(POW_fixture[vm.fork][str(i)]["nonce"])
            mix_hash = bytes.fromhex(POW_fixture[vm.fork][str(i)]["mix_hash"])
            block = chain.mine_block(nonce=nonce, mix_hash=mix_hash)
            total_num_tx = total_num_tx + len(block.transactions)
            total_gas_used = total_gas_used + block.header.gas_used

        return total_gas_used, total_num_tx


def mine_block(chain: MiningChain, block_number: int, random_address: bool) -> None:
    header = chain.get_block().header
    tx_gas_est = chain.estimate_gas(make_transaction(chain, random_address, 21000))
    while True:
        tx = make_transaction(chain, random_address, tx_gas_est)
        logging.debug('Applying Transaction {}'.format(tx))
        block, receipt, computation = chain.apply_transaction(tx)
        logging.debug('Block {}'.format(block))
        logging.debug('Receipt {}'.format(receipt))
        logging.debug('Computation {}'.format(computation))
        assert computation.is_success
        if header.gas_limit <= receipt.gas_used + tx_gas_est:
            break;


def make_transaction(chain: MiningChain, random_address: bool, tx_gas_est: int) -> BaseTransaction:

    if random_address:
        to_address = generate_random_address()
    else:
        to_address = SECOND_ACCOUNT.address
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FIRST_ACCOUNT.private_key,
        from_=FIRST_ACCOUNT.address,
        to=to_address,
        amount=100,
        gas=tx_gas_est,
        data=b'',
    )
    return tx


class ValueTransfer(BaseBenchmark):

    def __init__(self, benchmark: Callable, db: DB, num_blocks: int, validate_POW: bool, make_POW_fixture: bool) -> None:
        self.name =re.search(r'\s(\w+)\s',
                              str(benchmark)
                              ).group(1).replace('_', ' ') + " value transfer"
        self.benchmark = benchmark
        self.db = db
        self.num_blocks = num_blocks
        self.validate_POW = validate_POW
        self.make_POW_fixture = make_POW_fixture
        self.POW_file_path = "scripts/benchmark/fixtures/ValueTransfer/"+ self.name.replace(" ", "_") +".json"
        self.POW_fixture = {}

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        #####  SETUP  #####
        # make the Proof of Work fixture
        if self.make_POW_fixture:
            make_POW_fixtures(self.benchmark, self.db, self.POW_file_path, self.num_blocks)
            logging.info("Generated Fixture")
            return total_stat

        # load fixtures
        with open(self.POW_file_path, 'r') as outfile:
            self.POW_fixture = json.load(outfile)

        for chain in get_all_chains(self.db, self.validate_POW):

            value = self.as_timed_result(lambda: self.benchmark(chain, self.POW_fixture, self.num_blocks))

            total_gas_used, total_num_tx = value.wrapped_value

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_tx=total_num_tx,
                total_seconds=value.duration,
                total_gas=total_gas_used,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat
