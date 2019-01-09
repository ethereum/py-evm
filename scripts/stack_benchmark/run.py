#!/usr/bin/env python

import pathlib

from eth_utils import (
    encode_hex,
    decode_hex,
)

from web3 import (
    Web3
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)

from scripts.benchmark._utils.chain_plumbing import (
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
    get_all_chains,
)
from scripts.benchmark._utils.compile import (
    get_compiled_contract
)
from scripts.benchmark._utils.tx import (
    new_transaction,
)

CONTRACT_FILE = 'scripts/stack_benchmark/contract_data/test_stack.sol'
CONTRACT_NAME = 'TestStack'
W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}
FIRST_TX_GAS_LIMIT = 367724
SECOND_TX_GAS_LIMIT = 62050


def execute_TestStack_contract():
    contract_interface = get_compiled_contract(
        pathlib.Path(CONTRACT_FILE),
        CONTRACT_NAME
    )
    w3 = Web3()

    # Get the chains
    chains = tuple(get_all_chains())
    chain = chains[0]

    # Instantiate the contract
    test_stack_contract = w3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin']
    )

    # Build transaction to deploy the contract
    w3_tx1 = test_stack_contract.constructor().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=FIRST_TX_GAS_LIMIT,
        data=decode_hex(w3_tx1['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)
    deployed_contract_address = computation.msg.storage_address
    assert computation.is_success

    # Interact with the deployed contract by calling the totalSupply() API ?????
    test_stack_contract = w3.eth.contract(
        address=Web3.toChecksumAddress(encode_hex(deployed_contract_address)),
        abi=contract_interface['abi'],
    )

    # Execute the computation
    w3_tx2 = test_stack_contract.functions.doLotsOfPops().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=deployed_contract_address,
        amount=0,
        gas=SECOND_TX_GAS_LIMIT,
        data=decode_hex(w3_tx2['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)
    # print(computation._memory._bytes)
    print(computation._stack.values)


def main():
    execute_TestStack_contract()


if __name__ == '__main__':
    main()
