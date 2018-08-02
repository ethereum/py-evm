#!/usr/bin/env python

import logging
import sys

from eth.utils.version import (
    construct_evm_runtime_identifier
)

from checks import (
    EmptyBlocks,
    ValueTransfer,
)

from checks.contract_interactions import (
    ContractInteractions,
    deploy_erc20,
    transfer_erc20,
    approve_erc20,
    transfer_from_erc20,
    deployed_erc20_contract,
    approved_erc20,
    deploy_dos,
    sstore_uint64_dos,
    create_empty_contract_dos,
    sstore_uint64_revert_dos,
    create_empty_contract_revert_dos,
    deployed_dos_contract,

)

from checks.empty_blocks import (
    Mine,
    Import,
)

from checks.simple_value_transfers import (
    Existing_address,
    Non_existing_address,
)

from contract_data import (
    get_contracts
)

from utils.chain_plumbing import (
    level_db,
    memory_db,
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

    make_POW_fixture = False
    if "--make_POW_fixtures" in sys.argv:
        make_POW_fixture = True

    total_stat = DefaultStat()

    benchmarks = [
        EmptyBlocks(benchmark=Mine,
            db=memory_db,
            num_blocks=500,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        EmptyBlocks(benchmark=Import,
            db=memory_db,
            num_blocks=500,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ValueTransfer(benchmark=Existing_address,
            db=memory_db,
            num_blocks=1,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ValueTransfer(benchmark=Non_existing_address,
            db=memory_db,
            num_blocks=1,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        # ERC20 contract interaction
        ContractInteractions(benchmark=deploy_erc20,
            setup=(None,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=transfer_erc20,
            setup=(deployed_erc20_contract,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=approve_erc20,
            setup=(deployed_erc20_contract,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=transfer_from_erc20,
            setup=(deployed_erc20_contract,approved_erc20),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        # DOS contract interaction
        ContractInteractions(benchmark=deploy_dos,
            setup=(None,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=sstore_uint64_dos,
            setup=(deployed_dos_contract,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=create_empty_contract_dos,
            setup=(deployed_dos_contract,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=sstore_uint64_revert_dos,
            setup=(deployed_dos_contract,),
            db=memory_db,
            num_blocks=100,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
        ContractInteractions(benchmark=create_empty_contract_revert_dos,
            setup=(deployed_dos_contract,),
            db=memory_db,
            num_blocks=100  ,
            num_tx=2,
            validate_POW=True,
            make_POW_fixture=make_POW_fixture),
    ]

    for benchmark in benchmarks:
        total_stat = total_stat.cumulate(benchmark.run(), increment_by_counter=True)

    print_final_benchmark_total_line(total_stat)

if __name__ == '__main__':
    run()
