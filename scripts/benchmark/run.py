#!/usr/bin/env python

import logging
import sys

from eth.utils.version import (
    construct_evm_runtime_identifier
)

from checks import (
    ImportEmptyBlocksBenchmark,
    MineEmptyBlocksBenchmark,
    SimpleValueTransferBenchmark,
)

from checks.erc20_interact import (
    ERC20DeployBenchmark,
    ERC20TransferBenchmark,
    ERC20ApproveBenchmark,
    ERC20TransferFromBenchmark,
)
from checks.deploy_dos import (
    DOSContractDeployBenchmark,
    DOSContractSstoreUint64Benchmark,
    DOSContractCreateEmptyContractBenchmark,
    DOSContractRevertSstoreUint64Benchmark,
    DOSContractRevertCreateEmptyContractBenchmark,
)

from checks.simple_value_transfers import (
    SimpleValueTransferBenchmarkConfig,
)

from contract_data import (
    get_contracts
)

from utils.chain_plumbing import (
    SECOND_ADDRESS,
)
from utils.compile import (
    compile_contracts
)
from utils.reporting import (
    DefaultStat,
    print_final_benchmark_total_line
)
from utils.shellart import (
    bold_green,
    bold_red,
)

DEFAULT_NUM_BLOCKS = 2
DEFAULT_NUM_TX = 1

TO_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=SECOND_ADDRESS,
    greeter_info='Sending to existing address\n',
    num_blocks=DEFAULT_NUM_BLOCKS,
    num_tx=DEFAULT_NUM_TX
)


TO_NON_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=None,
    greeter_info='Sending to non-existing address\n',
    num_blocks=DEFAULT_NUM_BLOCKS,
    num_tx=DEFAULT_NUM_TX
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

    if "--compile-contracts" in sys.argv:
        logging.info('Precompiling contracts')
        try:
            compile_contracts(get_contracts())
        except OSError:
            logging.error(bold_red('Compiling contracts requires "solc" system dependency'))
            sys.exit(1)

    total_stat = DefaultStat()

    benchmarks = [
        MineEmptyBlocksBenchmark(DEFAULT_NUM_BLOCKS),
        ImportEmptyBlocksBenchmark(DEFAULT_NUM_BLOCKS),
        SimpleValueTransferBenchmark(TO_EXISTING_ADDRESS_CONFIG),
        SimpleValueTransferBenchmark(TO_NON_EXISTING_ADDRESS_CONFIG),
        ERC20DeployBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        ERC20TransferBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        ERC20ApproveBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        ERC20TransferFromBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        DOSContractDeployBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        DOSContractSstoreUint64Benchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        DOSContractCreateEmptyContractBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        DOSContractRevertSstoreUint64Benchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
        DOSContractRevertCreateEmptyContractBenchmark(DEFAULT_NUM_BLOCKS, DEFAULT_NUM_TX),
    ]

    for benchmark in benchmarks:
        total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)

    print_final_benchmark_total_line(total_stat)


if __name__ == '__main__':
    run()
