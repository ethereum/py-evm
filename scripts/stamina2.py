import logging
import pathlib
import json
from pprint import pprint
from scripts.benchmark.utils.chain_plumbing import get_chain

from eth_keys import (
    keys
)

from eth_typing import (
    Address
)

from scripts.benchmark.utils.tx import (
    new_transaction,
)

from eth.vm.forks.byzantium import (
    ByzantiumVM,
)

from eth.chains.base import (
    MiningChain,
)

from web3 import (
    Web3
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

from solc import compile_source
from web3.contract import ConciseContract


with open("./scripts/stamina.sol", encoding='utf8') as f:
    contract_source_code = f.read()

DEFAULT_GAS_LIMIT = 180000
W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:30303"))

compiled_sol = compile_source(contract_source_code) # Compiled source code
contract_interface = compiled_sol['<stdin>:Stamina']
stamina_address = Web3.toChecksumAddress('0x000000000000000000000000000000000000dead')
stamina = w3.eth.contract(
    address=decode_hex(stamina_address),
    abi=contract_interface['abi'],
    bytecode=contract_interface['bin']
)

# same as FUNDED_ADDRESS_PRIVATE_KEY
delegatee_private_key = keys.PrivateKey(decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8'))
delegator_private_key = keys.PrivateKey(decode_hex('0x45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d0'))

delegatee = Address(delegatee_private_key.public_key.to_canonical_address())
delegator = Address(delegator_private_key.public_key.to_canonical_address())

stamina_contract = {"address":stamina_address,
                    "code":stamina.constructor().buildTransaction(W3_TX_DEFAULTS)['data']}

def run() -> None:
    # get Byzantium VM
    # set Accounts
    chain = get_chain(ByzantiumVM,
                      EOA=[delegator, delegatee],
                      CA=[stamina_contract])

    init_function(decode_hex(stamina_address), chain)
    initialized_function(decode_hex(stamina_address), chain)
    set_delegator_function(decode_hex(stamina_address), chain)
    get_delegatee_function(decode_hex(stamina_address), chain)
    deposit_function(decode_hex(stamina_address), chain)
    get_stamina_function(decode_hex(stamina_address), chain)

def init_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.init(10, 20, 50).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=0,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success

def initialized_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.initialized().buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=0,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1

def set_delegator_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.setDelegator(delegator).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=0,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1

def get_delegatee_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.getDelegatee(delegator).buildTransaction(W3_TX_DEFAULTS)

    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=0,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    # print(encode_hex(computation.output))
    # print(encode_hex(delegatee))

def deposit_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.deposit(delegatee).buildTransaction(W3_TX_DEFAULTS)

    # amount: 100
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=100,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 1

def get_stamina_function(addr: str, chain: MiningChain) -> None:
    w3_tx = stamina.functions.getStamina(delegatee).buildTransaction(W3_TX_DEFAULTS)

    # gas_price is gasPrice field
    tx = new_transaction(
        vm=chain.get_vm(),
        private_key=delegatee_private_key,
        from_=delegatee,
        to=addr,
        amount=0,
        gas=DEFAULT_GAS_LIMIT,
        data=decode_hex(w3_tx['data']),
    )

    block, receipt, computation = chain.apply_transaction(tx)

    assert computation.is_success
    assert to_int(computation.output) == 100

if __name__ == '__main__':
    run()
