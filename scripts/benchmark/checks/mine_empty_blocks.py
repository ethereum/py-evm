import logging

from eth.chains.base import (
    MiningChain,
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


class MineEmptyBlocksBenchmark(BaseBenchmark):
    def __init__(self, num_blocks: int = 500) -> None:
        self.num_blocks = num_blocks

    @property
    def name(self) -> str:
        return "Empty block mining"

    def execute(self) -> DefaultStat:
        total_stat = DefaultStat()

        for chain in get_all_chains():
            value = self.as_timed_result(
                lambda chain=chain: self.mine_empty_blocks(chain, self.num_blocks)
            )

            stat = DefaultStat(
                caption=chain.get_vm().fork,
                total_blocks=self.num_blocks,
                total_seconds=value.duration,
            )
            total_stat = total_stat.cumulate(stat)
            self.print_stat_line(stat)

        return total_stat

    def mine_empty_blocks(self, chain: MiningChain, number_blocks: int) -> None:
        for _ in range(1, number_blocks + 1):
            block = chain.mine_block()
            logging.debug(format_block(block))
