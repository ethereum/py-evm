import logging
import pathlib
from typing import (
    Tuple,
    Callable,
    Any,
)

from web3 import (
    Web3,
    utils as w3_utils,
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)
from eth.chains.base import (
    MiningChain,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from .base_benchmark import (
    BaseBenchmark,
)
from utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    SECOND_ADDRESS,
    SECOND_ADDRESS_PRIVATE_KEY,
    get_all_chains,
)
from utils.compile import (
    get_compiled_contract
)
from utils.reporting import (
    DefaultStat,
)
from utils.tx import (
    new_transaction,
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
CONTRACT_NAME = 'SimpleToken'

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

# checksum addresses for creating Web3 transactions
ADDR_1 = Web3.toChecksumAddress(FUNDED_ADDRESS)
ADDR_2 = Web3.toChecksumAddress(SECOND_ADDRESS)


class ERC20BenchmarkConfig:
    def __init__(self,
                 name: str,
                 setup_benchmark: Callable[..., Any],
                 benchmark_transaction: Callable[..., Any],) -> None:

        self.name = name
        self._setup_benchmark = setup_benchmark
        self._benchmark_transaction = benchmark_transaction

        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE),
            CONTRACT_NAME
        )
        self.w3 = Web3()
        # will be defined after the contract is deployed
        self.deployed_contract_address: bytes
        self.simple_token: w3_utils.datatypes.Contract

    def setup_benchmark(self, chain: MiningChain) -> None:
        self._setup_benchmark(self, chain)
        chain.mine_block()

    def benchmark_transaction(self, chain: MiningChain) -> None:
        self._benchmark_transaction(self, chain)


########################
# ERC20 Setup Fucntions
########################
def no_setup(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    pass


def transfer_from_setup(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    erc_deploy(self, chain)
    erc_approve(self, chain)


########################
# Create ERC20 Transactions
########################
def erc_deploy(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    # Instantiate the contract
    SimpleToken = self.w3.eth.contract(
        abi=self.contract_interface['abi'],
        bytecode=self.contract_interface['bin']
    )
    # Build transaction to deploy the contract
    # build tx data using Web3
    w3_tx = SimpleToken.constructor().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=FIRST_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )
    logging.debug('Applying Transaction {}'.format(tx))
    # apply transaction to block
    block, receipt, computation = chain.apply_transaction(tx)
    # Keep track of deployed contract address
    self.deployed_contract_address = computation.msg.storage_address
    assert computation.is_success
    # Keep track of simple_token object for further interaction
    self.simple_token = self.w3.eth.contract(
        address=Web3.toChecksumAddress(encode_hex(self.deployed_contract_address)),
        abi=self.contract_interface['abi'],
    )


def erc_transfer(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    # build tx data using Web3
    w3_tx = self.simple_token.functions.transfer(
        ADDR_1,
        TRANSFER_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=self.deployed_contract_address,
        amount=0,
        gas=SECOND_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )
    # apply transaction to block
    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1


def erc_approve(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    # build tx data using Web3
    w3_tx = self.simple_token.functions.approve(
        ADDR_2,
        TRANSFER_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=self.deployed_contract_address,
        amount=0,
        gas=SECOND_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )
    # apply transaction to block
    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1


def erc_transfer_from(self: ERC20BenchmarkConfig, chain: MiningChain) -> None:
    # requires approve to be called in order to execute successfully
    # build tx data using Web3
    w3_tx = self.simple_token.functions.transferFrom(
        ADDR_1,
        ADDR_2,
        TRANSER_FROM_AMOUNT
    ).buildTransaction(W3_TX_DEFAULTS)
    # create transaction
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=SECOND_ADDRESS_PRIVATE_KEY,
        from_=SECOND_ADDRESS,
        to=self.deployed_contract_address,
        amount=0,
        gas=SECOND_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )
    # apply transaction to block
    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1


########################
# Configurations for ERC20 interactions
########################
ERC20_DEPLOY_CONFIG = ERC20BenchmarkConfig(
    'ERC20 deployment',
    no_setup,
    erc_deploy,)

ERC20_TRANSFER_CONFIG = ERC20BenchmarkConfig(
    'ERC20 transfer',
    erc_deploy,
    erc_transfer,)

ERC20_APPROVE_CONFIG = ERC20BenchmarkConfig(
    'ERC20 approve',
    erc_deploy,
    erc_approve,)

ERC20_TRANSFER_FROM_CONFIG = ERC20BenchmarkConfig(
    'ERC20 transfer from',
    transfer_from_setup,
    erc_transfer_from,)


class ERC20Benchmark(BaseBenchmark):
    def __init__(self,
                 config: ERC20BenchmarkConfig,
                 num_blocks: int = 100,
                 num_tx: int = 2) -> None:

        super().__init__()
        self.num_blocks = num_blocks
        self.num_tx = num_tx
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        for chain in get_all_chains():
            # Perform prepartions on the chain that do not count into the benchmark time
            self.config.setup_benchmark(chain)

            # Perform the actual work that is measured
            value = self.as_timed_result(
                lambda: self.mine_blocks(chain, self.num_blocks, self.num_tx)
            )
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

    def mine_blocks(self,
                    chain: MiningChain,
                    num_blocks: int,
                    num_tx: int) -> Tuple[int, int]:

        total_gas_used = 0
        total_num_tx = 0
        for i in range(1, num_blocks + 1):
            block = self.mine_block(chain, i, num_tx)
            total_gas_used = total_gas_used + block.header.gas_used
            total_num_tx = total_num_tx + len(block.transactions)
        return total_gas_used, total_num_tx

    def mine_block(self,
                   chain: MiningChain,
                   block_number: int,
                   num_tx: int) -> BaseBlock:

        for _ in range(1, num_tx + 1):
            self.config.benchmark_transaction(chain)

        return chain.mine_block()
