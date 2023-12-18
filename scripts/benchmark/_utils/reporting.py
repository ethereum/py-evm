import logging
from typing import (
    NamedTuple,
)

from scripts.benchmark._utils.shellart import (
    bold_white,
)


class DefaultStat(NamedTuple):
    counter: int = 0
    caption: str = ""
    total_tx: int = 0
    total_blocks: int = 0
    total_seconds: int = 0
    total_gas: int = 0

    @property
    def tx_per_second(self) -> float:
        return self.total_tx / self.total_seconds

    @property
    def blocks_per_second(self) -> float:
        return self.total_blocks / self.total_seconds

    @property
    def gas_per_second(self) -> float:
        return self.total_gas / self.total_seconds

    @property
    def avg_total_tx(self) -> float:
        return self.total_tx / self.counter

    @property
    def avg_total_blocks(self) -> float:
        return self.total_blocks / self.counter

    @property
    def avg_total_seconds(self) -> float:
        return self.total_seconds / self.counter

    @property
    def avg_total_gas(self) -> float:
        return self.total_gas / self.counter

    def cumulate(
        self, stat: "DefaultStat", increment_by_counter: bool = False
    ) -> "DefaultStat":
        increment_step = 1 if not increment_by_counter else stat.counter
        return DefaultStat(
            counter=self.counter + increment_step,
            total_tx=self.total_tx + stat.total_tx,
            total_blocks=self.total_blocks + stat.total_blocks,
            total_seconds=self.total_seconds + stat.total_seconds,
            total_gas=self.total_gas + stat.total_gas,
        )


REPORT_TABLE_LENGTH = 144
SINGLE_UNDERLINE = "-" * REPORT_TABLE_LENGTH
DOUBLE_UNDERLINE = "=" * REPORT_TABLE_LENGTH
HASH_UNDERLINE = "#" * REPORT_TABLE_LENGTH


def print_default_benchmark_result_header() -> None:
    logging.info(SINGLE_UNDERLINE)
    logging.info(
        bold_white(
            f"|{'VM':^19}|{'total seconds':^16}|{'total tx':^16}"
            f"|{'tx / second':^16}|{'total blocks':^16}|{'blocks / second':^20}"
            f"|{'total gas':^16}|{'gas / second':^16}|"
        )
    )
    logging.info(SINGLE_UNDERLINE)


def print_default_benchmark_stat_line(stat: DefaultStat) -> None:
    logging.info(
        f"|{stat.caption:^19}"
        f"|{stat.total_seconds:^16.3f}"
        f"|{stat.total_tx:^16}"
        f"|{stat.tx_per_second:^16.3f}"
        f"|{stat.total_blocks:^16}"
        f"|{stat.blocks_per_second:^20.3f}"
        f"|{stat.total_gas:^16,}"
        f"|{stat.gas_per_second:^16,.3f}|"
    )


def print_default_benchmark_total_line(stat: DefaultStat) -> None:
    logging.info(SINGLE_UNDERLINE)
    logging.info(
        bold_white(
            f'|{"Total":^19}'  # caption
            f"|{stat.total_seconds:^16.3f}"
            f"|{stat.total_tx:^16}"
            f'|{"-":^16}'  # tx_per_second
            f"|{stat.total_blocks:^16}"
            f'|{"-":^20}'  # blocks_per_second
            f"|{stat.total_gas:^16,}"
            f'|{"-":^16}|'  # gas per second
        )
    )
    logging.info(
        bold_white(
            f'|{"Avg":^19}'
            f"|{stat.avg_total_seconds:^16.3f}"
            f"|{stat.avg_total_tx:^16.0f}"
            f"|{stat.tx_per_second:^16.3f}"
            f"|{stat.avg_total_blocks:^16.0f}"
            f"|{stat.blocks_per_second:^20.3f}"
            f"|{stat.avg_total_gas:^16,.0f}"
            f"|{stat.gas_per_second:^16,.3f}|"
        )
    )
    logging.info(DOUBLE_UNDERLINE + "\n")


def print_final_benchmark_total_line(stat: DefaultStat) -> None:
    logging.info(HASH_UNDERLINE + "\n")
    print_default_benchmark_total_line(stat)
