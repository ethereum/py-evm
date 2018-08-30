import pathlib
import logging
import json
import web3

from pprint import pprint
from web3 import Web3
from solc import compile_source
from web3.contract import ConciseContract

from scripts.benchmark.utils.chain_plumbing import (
    get_chain,
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)

from eth.vm.forks.byzantium import (
    ByzantiumVM,
)

from eth.vm.forks.frontier import (
    FrontierVM,
)

from eth.chains.base import (
    MiningChain,
)

from scripts.benchmark.utils.tx import (
    new_transaction,
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from scripts.benchmark.utils.compile import (
    get_compiled_contract
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:30303"))

contract_source_code = '''
pragma solidity ^0.4.23;


contract Stamina {
    uint256 a = 10;
}
'''

# TODO: split stamina contract

def run() -> None:
    # get Byzantium VM
    chain = get_chain(ByzantiumVM)
    _deploy_stamina(chain)

def _deploy_stamina(chain: MiningChain) -> None:
    compiled_sol = compile_source(contract_source_code) # Compiled source code
    contract_interface = compiled_sol['<stdin>:Stamina']

    # Instantiate and deploy contract
    Stamina = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

    # Build transaction to deploy the contract
    w3_tx = Stamina.constructor().buildTransaction(W3_TX_DEFAULTS)
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=CREATE_CONTRACT_ADDRESS,
        amount=0,
        gas=FIRST_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)
    # Keep track of deployed contract address
    deployed_contract_address = computation.msg.storage_address

    print(computation.is_success)
    assert computation.is_success

    state_root = chain.get_vm().state.account_db.state_root
    print(state_root)
    # code = chain.get_vm().state.account_db.get_code(deployed_contract_address)
    # print(code)
    # _call_function(deployed_contract_address, contract_interface, chain)

def _call_function(addr, contract_interface, chain) -> None:
    stamina = w3.eth.contract(
        address=addr,
        abi=contract_interface['abi']
    )

    w3_tx = stamina.functions.init().buildTransaction(W3_TX_DEFAULTS)
    # w3_tx = stamina.functions.development().buildTransaction(W3_TX_DEFAULTS)
    # w3_tx = stamina.functions.setDelegator(
    #     addr
    # ).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=FUNDED_ADDRESS_PRIVATE_KEY,
        from_=FUNDED_ADDRESS,
        to=addr,
        amount=0,
        gas=SECOND_TX_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    # assert computation.is_success

    # print(block)
    # print(computation.is_success)
    # print(computation.output)

if __name__ == '__main__':
    run()
