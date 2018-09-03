import logging
import pathlib
import json
from pprint import pprint
from scripts.benchmark.utils.chain_plumbing import (
    get_chain,
    FUNDED_ADDRESS,
    FUNDED_ADDRESS_PRIVATE_KEY,
)

from scripts.benchmark.utils.address import (
    generate_random_address,
)

from scripts.benchmark.utils.compile import (
    get_compiled_contract
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

from eth.constants import (
    CREATE_CONTRACT_ADDRESS
)

from eth_utils import (
    encode_hex,
    decode_hex,
    to_int,
)

FIRST_TX_GAS_LIMIT = 1400000
SECOND_TX_GAS_LIMIT = 60000
TRANSFER_AMOUNT = 1000
TRANSER_FROM_AMOUNT = 1

W3_TX_DEFAULTS = {'gas': 0, 'gasPrice': 0}

CONTRACT_FILE = 'scripts/benchmark/contract_data/erc20.sol'
CONTRACT_NAME = 'SimpleToken'

contract_interface = get_compiled_contract(
    pathlib.Path(CONTRACT_FILE),
    CONTRACT_NAME
)
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:30303"))

erc20test_address = Web3.toChecksumAddress('0x000000000000000000000000000000000000abcd')

def run() -> None:
    # get Byzantium VM
    chain = get_chain(ByzantiumVM)
    _erc_transfer(decode_hex(erc20test_address), chain)

def _erc_transfer(addr: str, chain: MiningChain) -> None:
    simple_token = w3.eth.contract(
        address=Web3.toChecksumAddress(encode_hex(addr)),
        abi=contract_interface['abi'],
    )

    w3_tx = simple_token.functions.transfer(
        addr,
        0
    ).buildTransaction(W3_TX_DEFAULTS)

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

    assert computation.is_success
    assert to_int(computation.output) == 1

    print(block)
    print(computation.is_success)
    print(computation.output)

if __name__ == '__main__':
    run()
