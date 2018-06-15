import logging
import pathlib
from typing import (
    Tuple
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
    Chain,
)
from evm.rlp.blocks import (
    BaseBlock,
)

from .base_benchmark import (
    BaseBenchmark,
)
from utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
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
SECOND_TX_GAS_LIMIT = 22000

CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
CONTRACT_NAME = 'SimpleToken'

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}


class DeployErc20(BaseBenchmark):

    def __init__(self, num_blocks: int = 100, num_tx: int = 2) -> None:
        super().__init__()

        self.num_blocks = num_blocks
        self.num_tx = num_tx

        self.contract_interface = get_compiled_contract(
            pathlib.Path(CONTRACT_FILE),
            CONTRACT_NAME
        )

        self.w3 = Web3()

    @property
    def name(self) -> str:
        return 'ERC20 deployment'

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        for chain in get_all_chains():

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

    def mine_blocks(self, chain: Chain, num_blocks: int, num_tx: int) -> Tuple[int, int]:
        total_gas_used = 0
        total_num_tx = 0

        for i in range(1, num_blocks + 1):
            block = self.mine_block(chain, i, num_tx)
            total_gas_used = total_gas_used + block.header.gas_used
            total_num_tx = total_num_tx + len(block.transactions)

        return total_gas_used, total_num_tx

    def mine_block(self,
                   chain: Chain,
                   block_number: int,
                   num_tx: int) -> BaseBlock:

        for i in range(1, num_tx + 1):
            self.apply_transaction(chain)

        return chain.mine_block()

    def apply_transaction(self, chain: Chain) -> None:

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
        deployed_contract_address = computation.msg.storage_address

        assert computation.is_success

        # Interact with the deployed contract by calling the totalSupply() API
        simple_token = self.w3.eth.contract(
            address=Web3.toChecksumAddress(encode_hex(deployed_contract_address)),
            abi=self.contract_interface['abi'],
        )
        w3_tx2 = simple_token.functions.totalSupply().buildTransaction(W3_TX_DEFAULTS)

        tx2 = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=deployed_contract_address,
            amount=0,
            gas=SECOND_TX_GAS_LIMIT,
            data=decode_hex(w3_tx2['data']),
        )

        block, receipt, computation = chain.apply_transaction(tx2)

        assert computation.is_success
        assert to_int(computation.output) == EXPECTED_TOTAL_SUPPLY
