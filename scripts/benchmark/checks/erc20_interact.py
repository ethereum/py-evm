from abc import (
    abstractmethod,
)
import pathlib
from typing import (
    Tuple,
)

from eth_utils import (
    decode_hex,
    encode_hex,
)
from web3 import (
    Web3,
)

from eth.chains.base import (
    MiningChain,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.tools.factories.transaction import (
    new_transaction,
)
from scripts.benchmark._utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    SECOND_ADDRESS,
    SECOND_ADDRESS_PRIVATE_KEY,
    get_all_chains,
)
from scripts.benchmark._utils.compile import (
    get_compiled_contract,
)
from scripts.benchmark._utils.reporting import (
    DefaultStat,
)

from .base_benchmark import (
    BaseBenchmark,
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

CONTRACT_FILE = "scripts/benchmark/contract_data/erc20.sol"
CONTRACT_NAME = "SimpleToken"

W3_TX_DEFAULTS = {"gas": 0, "gasPrice": 0}


class BaseERC20Benchmark(BaseBenchmark):
    def __init__(self, num_blocks: int = 2, num_tx: int = 50) -> None:
        super().__init__()

        self.num_blocks = num_blocks
        self.num_tx = num_tx
        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE), CONTRACT_NAME
        )
        self.w3 = Web3()
        self.addr1 = Web3.toChecksumAddress(FUNDED_ADDRESS)
        self.addr2 = Web3.toChecksumAddress(SECOND_ADDRESS)

    def _setup_benchmark(self, chain: MiningChain) -> None:
        """
        This hook can be overwritten to perform preparations on the chain
        that do not count into the measured benchmark time
        """

    @abstractmethod
    def _next_transaction(self, chain: MiningChain) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        for chain in get_all_chains():
            # Perform prepartions on the chain that do not count into the
            # benchmark time
            self._setup_benchmark(chain)

            # Perform the actual work that is measured
            value = self.as_timed_result(
                lambda chain=chain: self.mine_blocks(
                    chain, self.num_blocks, self.num_tx
                )
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

    def mine_blocks(
        self, chain: MiningChain, num_blocks: int, num_tx: int
    ) -> Tuple[int, int]:
        total_gas_used = 0
        total_num_tx = 0
        for i in range(1, num_blocks + 1):
            import_result = self.mine_block(chain, i, num_tx)
            block = import_result.imported_block
            total_gas_used = total_gas_used + block.header.gas_used
            total_num_tx = total_num_tx + len(block.transactions)
        return total_gas_used, total_num_tx

    def mine_block(
        self, chain: MiningChain, block_number: int, num_tx: int
    ) -> BaseBlock:
        transactions, callbacks = zip(
            *(self._next_transaction(chain) for _ in range(num_tx))
        )

        mining_result, receipts, computations = chain.mine_all(transactions)

        for callback, receipt, computation in zip(callbacks, receipts, computations):
            callback(receipt, computation)

        return mining_result

    def _deploy_simple_token(self, chain: MiningChain, nonce: int = None) -> None:
        # Instantiate the contract
        SimpleToken = self.w3.eth.contract(
            abi=self.contract_interface["abi"], bytecode=self.contract_interface["bin"]
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
            data=decode_hex(w3_tx["data"]),
            nonce=nonce,
        )

        def callback(receipt, computation) -> None:
            computation.raise_if_error()

            # Keep track of deployed contract address
            self.deployed_contract_address = computation.msg.storage_address

            # Keep track of simple_token object
            self.simple_token = self.w3.eth.contract(
                address=Web3.toChecksumAddress(
                    encode_hex(self.deployed_contract_address)
                ),
                abi=self.contract_interface["abi"],
            )

        return tx, callback

    def _erc_transfer(self, addr: str, chain: MiningChain, nonce: int = None) -> None:
        w3_tx = self.simple_token.functions.transfer(
            addr, TRANSFER_AMOUNT
        ).buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx["data"]),
            nonce=nonce,
        )

        def callback(receipt, computation) -> None:
            computation.raise_if_error()
            assert computation.output == b"\0" * 31 + b"\x01", computation.output

        return tx, callback

    def _erc_approve(self, addr2: str, chain: MiningChain, nonce: int = None) -> None:
        w3_tx = self.simple_token.functions.approve(
            addr2, TRANSFER_AMOUNT
        ).buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx["data"]),
            nonce=nonce,
        )

        def callback(receipt, computation) -> None:
            computation.raise_if_error()
            assert computation.output == b"\0" * 31 + b"\x01", computation.output

        return tx, callback

    def _erc_transfer_from(
        self, addr1: str, addr2: str, chain: MiningChain, nonce: int = None
    ) -> None:
        w3_tx = self.simple_token.functions.transferFrom(
            addr1, addr2, TRANSER_FROM_AMOUNT
        ).buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=SECOND_ADDRESS_PRIVATE_KEY,
            from_=SECOND_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx["data"]),
            nonce=nonce,
        )

        def callback(receipt, computation) -> None:
            computation.raise_if_error()
            assert computation.output == b"\0" * 31 + b"\x01", computation.output

        return tx, callback


class ERC20DeployBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()
        # Can only fit 2 deployments in a block
        self.num_tx = 2

    @property
    def name(self) -> str:
        return "ERC20 deployment"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._next_nonce = None

    def _next_transaction(self, chain: MiningChain) -> None:
        txn_info = self._deploy_simple_token(chain, self._next_nonce)
        txn = txn_info[0]
        self._next_nonce = txn.nonce + 1
        return txn_info


class ERC20TransferBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()
        self._next_nonce = None

    @property
    def name(self) -> str:
        return "ERC20 Transfer"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._next_nonce = None

        txn, callback = self._deploy_simple_token(chain)
        _, receipts, computations = chain.mine_all([txn])
        assert len(receipts) == 1
        assert len(computations) == 1
        callback(receipts[0], computations[0])

    def _next_transaction(self, chain: MiningChain) -> None:
        txn_info = self._erc_transfer(self.addr1, chain, self._next_nonce)
        txn = txn_info[0]
        self._next_nonce = txn.nonce + 1
        return txn_info


class ERC20ApproveBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "ERC20 Approve"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._next_nonce = None
        txn, callback = self._deploy_simple_token(chain)
        _, receipts, computations = chain.mine_all([txn])
        assert len(receipts) == 1
        assert len(computations) == 1
        callback(receipts[0], computations[0])

    def _next_transaction(self, chain: MiningChain) -> None:
        txn_info = self._erc_approve(self.addr2, chain, self._next_nonce)
        txn = txn_info[0]
        self._next_nonce = txn.nonce + 1
        return txn_info


class ERC20TransferFromBenchmark(BaseERC20Benchmark):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        return "ERC20 TransferFrom"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self._next_nonce = None
        txn, callback = self._deploy_simple_token(chain)
        _, receipts, computations = chain.mine_all([txn])
        assert len(receipts) == 1
        assert len(computations) == 1
        callback(receipts[0], computations[0])

        actions = [
            self._erc_transfer(self.addr1, chain, nonce=1),
            self._erc_approve(self.addr2, chain, nonce=2),
        ]
        transactions, callbacks = zip(*actions)
        _, receipts, computations = chain.mine_all(transactions)

        for callback, receipt, computation in zip(callbacks, receipts, computations):
            callback(receipt, computation)

    def _next_transaction(self, chain: MiningChain) -> None:
        txn_info = self._erc_transfer_from(
            self.addr1, self.addr2, chain, self._next_nonce
        )
        txn = txn_info[0]
        self._next_nonce = txn.nonce + 1
        return txn_info
