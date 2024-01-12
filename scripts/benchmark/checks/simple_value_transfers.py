import logging
from typing import (
    NamedTuple,
    Tuple,
)

from eth_typing import (
    Address,
)

from eth.chains.base import (
    MiningChain,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.tools.factories.transaction import (
    new_transaction,
)
from scripts.benchmark._utils.address import (
    generate_random_address,
)
from scripts.benchmark._utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    SECOND_ADDRESS,
    get_all_chains,
)
from scripts.benchmark._utils.reporting import (
    DefaultStat,
)
from scripts.benchmark._utils.shellart import (
    bold_yellow,
)

from .base_benchmark import (
    BaseBenchmark,
)


class SimpleValueTransferBenchmarkConfig(NamedTuple):
    to_address: Address
    greeter_info: str
    num_blocks: int = 2


TO_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=SECOND_ADDRESS, greeter_info="Sending to existing address\n"
)


TO_NON_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=None, greeter_info="Sending to non-existing address\n"
)

# TODO: Investigate why 21000 doesn't work
SIMPLE_VALUE_TRANSFER_GAS_COST = 22000


class SimpleValueTransferBenchmark(BaseBenchmark):
    def __init__(self, config: SimpleValueTransferBenchmarkConfig) -> None:
        self.config = config
        self._next_nonce = None

    @property
    def name(self) -> str:
        return "Simple value transfer"

    def print_result_header(self) -> None:
        logging.info(bold_yellow(self.config.greeter_info))
        super().print_result_header()

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()
        num_blocks = self.config.num_blocks

        for chain in get_all_chains():
            self._next_nonce = None

            value = self.as_timed_result(
                lambda chain=chain: self.mine_blocks(chain, num_blocks)
            )

            total_gas_used, total_num_tx = value.wrapped_value

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=num_blocks,
                total_tx=total_num_tx,
                total_seconds=value.duration,
                total_gas=total_gas_used,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat

    def mine_blocks(self, chain: MiningChain, num_blocks: int) -> Tuple[int, int]:
        total_gas_used = 0
        total_num_tx = 0

        for i in range(1, num_blocks + 1):
            num_tx = (
                chain.get_block().header.gas_limit // SIMPLE_VALUE_TRANSFER_GAS_COST
            )
            block = self.mine_block(chain, i, num_tx)
            total_num_tx = total_num_tx + len(block.transactions)
            total_gas_used = total_gas_used + block.header.gas_used

        return total_gas_used, total_num_tx

    def mine_block(
        self, chain: MiningChain, block_number: int, num_tx: int
    ) -> BaseBlock:
        actions = [self.next_transaction(chain) for _ in range(num_tx)]

        transactions, callbacks = zip(*actions)

        mining_result, receipts, computations = chain.mine_all(transactions)

        for callback, receipt, computation in zip(callbacks, receipts, computations):
            callback(receipt, computation)

        return mining_result.imported_block

    def next_transaction(self, chain: MiningChain) -> None:
        if self.config.to_address is None:
            to_address = generate_random_address()
        else:
            to_address = self.config.to_address

        tx = new_transaction(
            vm=chain.get_vm(),
            private_key=FUNDED_ADDRESS_PRIVATE_KEY,
            from_=FUNDED_ADDRESS,
            to=to_address,
            amount=100,
            data=b"",
            nonce=self._next_nonce,
        )
        logging.debug(f"Built Transaction {tx}")

        self._next_nonce = tx.nonce + 1

        def callback(receipt, computation) -> None:
            logging.debug(f"Receipt {receipt}")
            logging.debug(f"Computation {computation}")

        return tx, callback
