import logging
import pathlib
from typing import (
    Tuple,
)

from abc import (
    abstractmethod,
)

from web3 import (
    Web3
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from evm.constants import (
    CREATE_CONTRACT_ADDRESS
)
from evm.chains.base import (
    MiningChain,
)
from evm.rlp.blocks import (
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
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


EXPECTED_TOTAL_SUPPLY = 10000000000000000000000
FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000

CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
CONTRACT_NAME = 'SimpleToken'

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}


class ERC20Interact():
    def __init__(self) -> None:
        chains = Persistant()
        self.benchmarks = [
            ERC20DeployBenchmark(chains),
            ERC20TransferBenchmark(chains),
            ERC20ApproveBenchmark(chains),
            ERC20TransferFromBenchmark(chains),
        ]

    def run(self) -> DefaultStat:
        total_stat = DefaultStat()
        for benchmark in self.benchmarks:
            total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)
        return total_stat


class Persistant():
    def __init__(self) -> None:
        self.persistant_chains = [chain for chain in get_all_chains()]
        self.deployed_contract_address = None
        self.simple_token = None

    def getChains(self):
        for chain in self.persistant_chains:
            yield chain

    def setHead(self, chain: MiningChain, head: BlockHeader) -> None:
        chain = self.persistant_chains[self.persistant_chains.index(chain)]
        chain.header = head
        chain.chaindb._set_as_canonical_chain_head(
            chain.chaindb.get_canonical_block_header_by_number(
                chain.header.block_number - 1))


class BaseERC20Benchmark(BaseBenchmark):

    def __init__(self, persist: Persistant, num_blocks: int = 100, num_tx: int = 2) -> None:
        super().__init__()

        self.num_blocks = num_blocks
        self.num_tx = num_tx
        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE),
            CONTRACT_NAME
        )
        self.persist = persist
        self.w3 = Web3()
        # store the chains, so they dont need to be created every time
        self.addr1 = Web3.toChecksumAddress(FUNDED_ADDRESS)
        self.addr2 = Web3.toChecksumAddress(SECOND_ADDRESS)

    @property
    @abstractmethod
    def name(self) -> DefaultStat:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def _setup_benchmark(self, chain: MiningChain) -> None:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def _do_benchmark(self, chain: MiningChain) -> None:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    def execute(self) -> DefaultStat:

        total_stat = DefaultStat()

        for chain in self.persist.getChains():
            # self._setup_benchmark(chain);

            value = self.as_timed_result(
                lambda: self.mine_blocks(chain, self.num_blocks, self.num_tx)
            )
            self.persist.setHead(chain, self.header_reset)

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

    def mine_blocks(self, chain: MiningChain, num_blocks: int, num_tx: int) -> Tuple[int, int]:
        total_gas_used = 0
        total_num_tx = 0
        for i in range(1, num_blocks + 1):
            block = self.mine_block(chain, i, num_tx)
            total_gas_used = total_gas_used + block.header.gas_used
            total_num_tx = total_num_tx + len(block.transactions)
            if (i == 1):
                self.header_reset = chain.header

        return total_gas_used, total_num_tx

    def mine_block(self,
                   chain: MiningChain,
                   block_number: int,
                   num_tx: int) -> BaseBlock:

        for i in range(1, num_tx + 1):
            self.apply_transaction(chain)

        return chain.mine_block()

    def apply_transaction(self, chain: MiningChain) -> None:

        self._do_benchmark(chain)

    def deploy_simple_token(self, chain: MiningChain) -> None:

        # Instantiate the contract
        SimpleToken = self.w3.eth.contract(
            abi=self.contract_interface['abi'],
            bytecode=self.contract_interface['bin']
        )

        # Build transaction to deploy the contract
        w3_tx1 = SimpleToken.constructor().buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=CREATE_CONTRACT_ADDRESS,
            amount=0,
            gas=FIRST_TX_GAS_LIMIT,
            data=decode_hex(w3_tx1['data']),
        )

        logging.debug('Applying Transaction {}'.format(tx))

        block, receipt, computation = chain.apply_transaction(tx)
        self.deployed_contract_address = computation.msg.storage_address

        if self.persist.deployed_contract_address is None:
            self.persist.deployed_contract_address = self.deployed_contract_address

        assert computation.is_success

        self.simple_token = self.w3.eth.contract(
            address=Web3.toChecksumAddress(encode_hex(self.deployed_contract_address)),
            abi=self.contract_interface['abi'],)

        if self.persist.simple_token is None:
            self.persist.simple_token = self.simple_token

    def erc_transfer(self, addr: str, chain: MiningChain) -> None:
        ammout = self.num_blocks * self.num_tx

        w3_tx1 = self.persist.simple_token.functions.transfer(
            addr, ammout).buildTransaction(W3_TX_DEFAULTS)

        tx1 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.persist.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx1['data']),
        )

        block, receipt, computation = chain.apply_transaction(tx1)

        assert computation.is_success
        assert to_int(computation.output) == 1

    def erc_approve(self, addr2: str, chain: MiningChain) -> None:
        ammout = self.num_blocks * self.num_tx

        w3_tx2 = self.persist.simple_token.functions.approve(
            addr2, ammout).buildTransaction(W3_TX_DEFAULTS)

        tx2 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.persist.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx2['data']),
        )

        block, receipt, computation = chain.apply_transaction(tx2)

        assert computation.is_success
        assert to_int(computation.output) == 1

    def erc_transfer_from(self, addr1: str, addr2: str, chain: MiningChain) -> None:

        w3_tx3 = self.persist.simple_token.functions.transferFrom(
            addr1, addr2, 1).buildTransaction(W3_TX_DEFAULTS)

        tx3 = new_transaction(
            vm=chain.get_vm(),
            private_key=SECOND_ADDRESS_PRIVATE_KEY,
            from_=SECOND_ADDRESS,
            to=self.persist.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx3['data']),
        )

        block, receipt, computation = chain.apply_transaction(tx3)

        assert computation.is_success
        assert to_int(computation.output) == 1


class ERC20DeployBenchmark(BaseERC20Benchmark):
    def __init__(self, persist: Persistant) -> None:
        super().__init__(persist)

    @property
    def name(self) -> str:
        return 'ERC20 deployment'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        return

    def _do_benchmark(self, chain: MiningChain) -> None:
        self.deploy_simple_token(chain)


class ERC20TransferBenchmark(BaseERC20Benchmark):
    def __init__(self, persist: Persistant) -> None:
        super().__init__(persist)

    @property
    def name(self) -> str:
        return 'ERC20 Transfer'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_simple_token(chain)
        chain.mine_block()
        return

    def _do_benchmark(self, chain: MiningChain) -> None:
        self.erc_transfer(self.addr1, chain)


class ERC20ApproveBenchmark(BaseERC20Benchmark):
    def __init__(self, persist: Persistant) -> None:
        super().__init__(persist)

    @property
    def name(self) -> str:
        return 'ERC20 Approve'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_simple_token(chain)
        self.erc_transfer(self.addr1, chain)
        chain.mine_block()
        return

    def _do_benchmark(self, chain: MiningChain) -> None:
        self.erc_approve(self.addr2, chain)


class ERC20TransferFromBenchmark(BaseERC20Benchmark):
    def __init__(self, persist: Persistant) -> None:
        super().__init__(persist)

    @property
    def name(self) -> str:
        return 'ERC20 TransferFrom'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_simple_token(chain)
        self.erc_transfer(self.addr1, chain)
        self.erc_approve(self.addr2, chain)
        chain.mine_block()
        return

    def _do_benchmark(self, chain: MiningChain) -> None:
        self.erc_transfer_from(self.addr1, self.addr2, chain)
