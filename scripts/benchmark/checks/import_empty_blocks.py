import logging

from eth.chains.base import (
    Chain,
)
from scripts.benchmark._utils.chain_plumbing import (
    get_all_chains,
)
from scripts.benchmark._utils.format import (
    format_block,
)
from scripts.benchmark._utils.reporting import (
    DefaultStat,
)

from .base_benchmark import (
    BaseBenchmark,
)


class ImportEmptyBlocksBenchmark(BaseBenchmark):
    def __init__(self, num_blocks: int = 500) -> None:
        self.num_blocks = num_blocks

    @property
    def name(self) -> str:
        return "Empty block import"

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        for chain in get_all_chains():
            val = self.as_timed_result(
                lambda chain=chain: self.import_empty_blocks(chain, self.num_blocks)
            )
            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_seconds=val.duration,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat

    def import_empty_blocks(self, chain: Chain, number_blocks: int) -> int:
        total_gas_used = 0
        for _ in range(1, number_blocks + 1):
            block = chain.import_block(chain.get_vm().get_block(), False).imported_block

            total_gas_used = total_gas_used + block.header.gas_used
            logging.debug(format_block(block))

        return total_gas_used
