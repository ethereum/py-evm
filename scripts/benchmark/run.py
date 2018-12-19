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

NUM_BLOCKS_TO_BENCHMARK = 2
NUM_TX_TO_BENCHMARK = 1

TO_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=SECOND_ADDRESS,
    greeter_info='Sending to existing address\n',
    num_blocks=NUM_BLOCKS_TO_BENCHMARK,
    num_tx=NUM_TX_TO_BENCHMARK
)


TO_NON_EXISTING_ADDRESS_CONFIG = SimpleValueTransferBenchmarkConfig(
    to_address=None,
    greeter_info='Sending to non-existing address\n',
    num_blocks=NUM_BLOCKS_TO_BENCHMARK,
    num_tx=NUM_TX_TO_BENCHMARK
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
        MineEmptyBlocksBenchmark(NUM_BLOCKS_TO_BENCHMARK),
        ImportEmptyBlocksBenchmark(NUM_BLOCKS_TO_BENCHMARK),
        SimpleValueTransferBenchmark(TO_EXISTING_ADDRESS_CONFIG),
        SimpleValueTransferBenchmark(TO_NON_EXISTING_ADDRESS_CONFIG),
        ERC20DeployBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        ERC20TransferBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        ERC20ApproveBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        ERC20TransferFromBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        DOSContractDeployBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        DOSContractSstoreUint64Benchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        DOSContractCreateEmptyContractBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        DOSContractRevertSstoreUint64Benchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
        DOSContractRevertCreateEmptyContractBenchmark(NUM_BLOCKS_TO_BENCHMARK, NUM_TX_TO_BENCHMARK),
    ]

    for benchmark in benchmarks:
        total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)

    print_final_benchmark_total_line(total_stat)


if __name__ == '__main__':
    run()
