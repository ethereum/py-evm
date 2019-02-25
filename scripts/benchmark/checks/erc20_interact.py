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
from _utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    SECOND_ADDRESS,
    SECOND_ADDRESS_PRIVATE_KEY,
    get_all_chains,
)
from _utils.compile import (
    get_compiled_contract
)
from _utils.reporting import (
    DefaultStat,
)
from _utils.tx import (
    new_transaction,
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
CONTRACT_NAME = 'SimpleToken'

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}


class BaseERC20Benchmark(BaseBenchmark):

    def __init__(self, num_blocks: int = 100, num_tx: int = 2) -> None:
        super().__init__()

        self.num_blocks = num_blocks
        self.num_tx = num_tx
        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE),
            CONTRACT_NAME
        )
        self.w3 = Web3()
        self.addr1 = Web3.toChecksumAddress(FUNDED_ADDRESS)
        self.addr2 = Web3.toChecksumAddress(SECOND_ADDRESS)

    def _setup_benchmark(self, chain: MiningChain) -> None:
        """
        This hook can be overwritten to perform preparations on the chain
        that do not count into the measured benchmark time
        """
        pass

    @abstractmethod
    def _apply_transaction(self, chain: MiningChain) -> None:
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        for chain in get_all_chains():
            # Perform prepartions on the chain that do not count into the
            # benchmark time
            self._setup_benchmark(chain)

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

    def mine_blocks(self, chain: MiningChain, num_blocks: int, num_tx: int) -> Tuple[int, int]:
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
            self._apply_transaction(chain)
        return chain.mine_block()

    def _deploy_simple_token(self, chain: MiningChain) -> None:
        # Instantiate the contract
        SimpleToken = self.w3.eth.contract(
            abi=self.contract_interface['abi'],
            bytecode=self.contract_interface['bin']
        )
        # Build transaction to deploy the contract
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
        block, receipt, computation = chain.apply_transaction(tx)
        # Keep track of deployed contract address
        self.deployed_contract_address = computation.msg.storage_address

        assert computation.is_success
        # Keep track of simple_token object
        self.simple_token = self.w3.eth.contract(
            address=Web3.toChecksumAddress(encode_hex(self.deployed_contract_address)),
            abi=self.contract_interface['abi'],
        )

    def _erc_transfer(self, addr: str, chain: MiningChain) -> None:
        w3_tx = self.simple_token.functions.transfer(
            addr,
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

        block, receipt, computation = chain.apply_transaction(tx)

        assert computation.is_success
        assert to_int(computation.output) == 1

    def _erc_approve(self, addr2: str, chain: MiningChain) -> None:
        w3_tx = self.simple_token.functions.approve(
            addr2,
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

        block, receipt, computation = chain.apply_transaction(tx)

        assert computation.is_success
        assert to_int(computation.output) == 1

    def _erc_transfer_from(self, addr1: str, addr2: str, chain: MiningChain) -> None:

        w3_tx = self.simple_token.functions.transferFrom(
            addr1,
            addr2,
            TRANSER_FROM_AMOUNT
        ).buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=SECOND_ADDRESS_PRIVATE_KEY,
            from_=SECOND_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx['data']),
        )

        block, receipt, computation = chain.apply_transaction(tx)

        assert computation.is_success
        assert to_int(computation.output) == 1


class ERC20DeployBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return 'ERC20 deployment'

    def _apply_transaction(self, chain: MiningChain) -> None:
        self._deploy_simple_token(chain)


class ERC20TransferBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return 'ERC20 Transfer'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._deploy_simple_token(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self._erc_transfer(self.addr1, chain)


class ERC20ApproveBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return 'ERC20 Approve'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._deploy_simple_token(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self._erc_approve(self.addr2, chain)


class ERC20TransferFromBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return 'ERC20 TransferFrom'

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._deploy_simple_token(chain)
        self._erc_transfer(self.addr1, chain)
        self._erc_approve(self.addr2, chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self._erc_transfer_from(self.addr1, self.addr2, chain)
