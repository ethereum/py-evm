#!/usr/bin/env python

import logging
import sys

from checks import (
    ImportEmptyBlocksBenchmark,
    MineEmptyBlocksBenchmark,
    SimpleValueTransferBenchmark,
)
from checks.deploy_dos import (
    DOSContractCreateEmptyContractBenchmark,
    DOSContractDeployBenchmark,
    DOSContractRevertCreateEmptyContractBenchmark,
    DOSContractRevertSstoreUint64Benchmark,
    DOSContractSstoreUint64Benchmark,
)
from checks.erc20_interact import (
    ERC20ApproveBenchmark,
    ERC20DeployBenchmark,
    ERC20TransferBenchmark,
    ERC20TransferFromBenchmark,
)
from checks.simple_value_transfers import (
    TO_EXISTING_ADDRESS_CONFIG,
    TO_NON_EXISTING_ADDRESS_CONFIG,
)
from contract_data import (
    get_contracts,
)

from eth._utils.version import (
    construct_evm_runtime_identifier,
)
from scripts.benchmark._utils.compile import (
    compile_contracts,
)
from scripts.benchmark._utils.reporting import (
    DefaultStat,
    print_final_benchmark_total_line,
)
from scripts.benchmark._utils.shellart import (
    bold_green,
    bold_red,
)

HEADER = (
    "\n"
    "██████  ███████ ███    ██  ██████ ██   ██ ███    ███  █████  ██████  ██   ██\n"
    "██   ██ ██      ████   ██ ██      ██   ██ ████  ████ ██   ██ ██   ██ ██  ██ \n"
    "██████  █████   ██ ██  ██ ██      ███████ ██ ████ ██ ███████ ██████  █████  \n"
    "██   ██ ██      ██  ██ ██ ██      ██   ██ ██  ██  ██ ██   ██ ██   ██ ██  ██ \n"
    "██████  ███████ ██   ████  ██████ ██   ██ ██      ██ ██   ██ ██   ██ ██   ██\n"
)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(bold_green(HEADER))
    logging.info(construct_evm_runtime_identifier() + "\n")

    if "--compile-contracts" in sys.argv:
        logging.info("Precompiling contracts")
        try:
            compile_contracts(get_contracts())
        except OSError:
            logging.error(
                bold_red('Compiling contracts requires "solc" system dependency')
            )
            sys.exit(1)

    total_stat = DefaultStat()

    benchmarks = [
        MineEmptyBlocksBenchmark(),
        ImportEmptyBlocksBenchmark(),
        SimpleValueTransferBenchmark(TO_EXISTING_ADDRESS_CONFIG),
        SimpleValueTransferBenchmark(TO_NON_EXISTING_ADDRESS_CONFIG),
        ERC20DeployBenchmark(),
        ERC20TransferBenchmark(),
        ERC20ApproveBenchmark(),
        ERC20TransferFromBenchmark(),
        DOSContractDeployBenchmark(),
        DOSContractSstoreUint64Benchmark(),
        DOSContractCreateEmptyContractBenchmark(),
        DOSContractRevertSstoreUint64Benchmark(),
        DOSContractRevertCreateEmptyContractBenchmark(),
    ]

    for benchmark in benchmarks:
        total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)

    print_final_benchmark_total_line(total_stat)


if __name__ == "__main__":
    run()
