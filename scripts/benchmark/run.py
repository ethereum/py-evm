#!/usr/bin/env python

import logging

from evm.utils.version import (
    construct_evm_runtime_identifier
)

from checks import (
    ImportEmptyBlocksBenchmark,
    MineEmptyBlocksBenchmark,
    SimpleValueTransferBenchmark,
)

from checks.simple_value_transfers import (
    TO_EXISTING_ADDRESS_CONFIG,
    TO_NON_EXISTING_ADDRESS_CONFIG
)

from utils.reporting import (
    DefaultStat,
    print_final_benchmark_total_line
)
from utils.shellart import (
    bold_green
)

HEADER = (
    "\n"
    "______                 _                          _     \n"
    "| ___ \               | |                        | |    \n"
    "| |_/ / ___ _ __   ___| |__  _ __ ___   __ _ _ __| | __ \n"
    "| ___ \/ _ \ '_ \ / __| '_ \| '_ ` _ \ / _` | '__| |/ / \n"
    "| |_/ /  __/ | | | (__| | | | | | | | | (_| | |  |   <  \n"
    "\____/ \___|_| |_|\___|_| |_|_| |_| |_|\__,_|_|  |_|\_\\\n"
)


def run() -> None:

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logging.info(bold_green(HEADER))
    logging.info(construct_evm_runtime_identifier() + "\n")

    total_stat = DefaultStat()

    benchmarks = [
        MineEmptyBlocksBenchmark(),
        ImportEmptyBlocksBenchmark(),
        SimpleValueTransferBenchmark(TO_EXISTING_ADDRESS_CONFIG),
        SimpleValueTransferBenchmark(TO_NON_EXISTING_ADDRESS_CONFIG),
    ]

    for benchmark in benchmarks:
        total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)

    print_final_benchmark_total_line(total_stat)


if __name__ == '__main__':
    run()
