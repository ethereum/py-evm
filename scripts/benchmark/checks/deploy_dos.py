from abc import (
    abstractmethod,
)
import logging
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

FIRST_TX_GAS_LIMIT = 367724
SECOND_TX_GAS_LIMIT = 65642  # Until Berlin, 63042 was sufficient
THIRD_TX_GAS_LIMIT = 108381  # Until Berlin, 105781 was sufficient
FORTH_TX_GAS_LIMIT = 21272
FIFTH_TX_GAS_LIMIT = 21272

CONTRACT_FILE = "scripts/benchmark/contract_data/DOSContract.sol"
CONTRACT_NAME = "DOSContract"

W3_TX_DEFAULTS = {"gas": 0, "gasPrice": 0}


class BaseDOSContractBenchmark(BaseBenchmark):
    def __init__(self, num_blocks: int = 3, num_tx: int = 3) -> None:
        super().__init__()

        self.num_blocks = num_blocks
        self.num_tx = num_tx

        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE), CONTRACT_NAME
        )

        self.w3 = Web3()

    def _setup_benchmark(self, chain: MiningChain) -> None:
        """
        This hook can be overwritten to perform preparations on the chain
        that do not count into the measured benchmark time
        """

    @abstractmethod
    def _apply_transaction(self, chain: MiningChain) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        for chain in get_all_chains():
            self._setup_benchmark(chain)

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

        blocks = tuple(
            self.mine_block(chain, i, num_tx) for i in range(1, num_blocks + 1)
        )
        total_gas_used = sum(block.header.gas_used for block in blocks)
        total_num_tx = sum(len(block.transactions) for block in blocks)

        return total_gas_used, total_num_tx

    def mine_block(
        self, chain: MiningChain, block_number: int, num_tx: int
    ) -> BaseBlock:
        for _ in range(1, num_tx + 1):
            self._apply_transaction(chain)

        return chain.mine_block()

    def deploy_dos_contract(self, chain: MiningChain) -> None:
        # Instantiate the contract
        dos_contract = self.w3.eth.contract(
            abi=self.contract_interface["abi"], bytecode=self.contract_interface["bin"]
        )

        # Build transaction to deploy the contract
        w3_tx1 = dos_contract.constructor().buildTransaction(W3_TX_DEFAULTS)

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=CREATE_CONTRACT_ADDRESS,
            amount=0,
            gas=FIRST_TX_GAS_LIMIT,
            data=decode_hex(w3_tx1["data"]),
        )

        logging.debug(f"Applying Transaction {tx}")

        block, receipt, computation = chain.apply_transaction(tx)
        self.deployed_contract_address = computation.msg.storage_address

        computation.raise_if_error()

        # Interact with the deployed contract by calling the totalSupply() API ?????
        self.dos_contract = self.w3.eth.contract(
            address=Web3.toChecksumAddress(encode_hex(self.deployed_contract_address)),
            abi=self.contract_interface["abi"],
        )

    def sstore_uint64(self, chain: MiningChain) -> None:
        w3_tx2 = self.dos_contract.functions.storageEntropy().buildTransaction(
            W3_TX_DEFAULTS
        )

        tx2 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx2["data"]),
        )

        block, receipt, computation = chain.apply_transaction(tx2)

        computation.raise_if_error()

    def create_empty_contract(self, chain: MiningChain) -> None:
        w3_tx3 = self.dos_contract.functions.createEmptyContract().buildTransaction(
            W3_TX_DEFAULTS
        )

        tx3 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=THIRD_TX_GAS_LIMIT,
            data=decode_hex(w3_tx3["data"]),
        )

        block, receipt, computation = chain.apply_transaction(tx3)

        computation.raise_if_error()

    def sstore_uint64_revert(self, chain: MiningChain) -> None:
        w3_tx4 = self.dos_contract.functions.storageEntropyRevert().buildTransaction(
            W3_TX_DEFAULTS
        )

        tx4 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=FORTH_TX_GAS_LIMIT,
            data=decode_hex(w3_tx4["data"]),
        )

        block, receipt, computation = chain.apply_transaction(tx4)

    def create_empty_contract_revert(self, chain: MiningChain) -> None:
        w3_tx5 = (
            self.dos_contract.functions.createEmptyContractRevert().buildTransaction(
                W3_TX_DEFAULTS
            )
        )

        tx5 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=self.deployed_contract_address,
            amount=0,
            gas=FIFTH_TX_GAS_LIMIT,
            data=decode_hex(w3_tx5["data"]),
        )

        block, receipt, computation = chain.apply_transaction(tx5)


class DOSContractDeployBenchmark(BaseDOSContractBenchmark):
    @property
    def name(self) -> str:
        return "DOSContract deployment"

    def _apply_transaction(self, chain: MiningChain) -> None:
        self.deploy_dos_contract(chain)


class DOSContractSstoreUint64Benchmark(BaseDOSContractBenchmark):
    @property
    def name(self) -> str:
        return "DOSContract sstore uint64"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_dos_contract(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self.sstore_uint64(chain)


class DOSContractCreateEmptyContractBenchmark(BaseDOSContractBenchmark):
    @property
    def name(self) -> str:
        return "DOSContract empty contract deployment"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_dos_contract(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self.create_empty_contract(chain)


class DOSContractRevertSstoreUint64Benchmark(BaseDOSContractBenchmark):
    @property
    def name(self) -> str:
        return "DOSContract revert empty sstore uint64"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_dos_contract(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self.sstore_uint64_revert(chain)


class DOSContractRevertCreateEmptyContractBenchmark(BaseDOSContractBenchmark):
    @property
    def name(self) -> str:
        return "DOScontract revert contract deployment"

    def _setup_benchmark(self, chain: MiningChain) -> None:
        self.deploy_dos_contract(chain)
        chain.mine_block()

    def _apply_transaction(self, chain: MiningChain) -> None:
        self.create_empty_contract_revert(chain)
