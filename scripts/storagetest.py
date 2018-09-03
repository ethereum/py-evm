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
pragma solidity ^0.4.24;

contract StorageTest {
  // saved at index 0
  uint storedUint256;

  // index 1
  // 0x1000000020000000000000004000000000000000000000000000000080: because each of items are packed
  uint128 storedUint128;
  uint64 storedUint64;
  uint32 storedUint32;
  uint16 storedUint16;

  // bytes(string) are left-aligned
  // index 2
	bytes16 storedBytes16;
                                     // get stored value: 0x62797465733136000000000000000000
  // index 3
	bytes32 storedBytes32;

  // index 4
	string storedString;
                                                 // 2a: length of the stored string
  // index 5
  bytes storedBytes;
                                              // 28: length of the stored bytes

  // index 6
  mapping (address => uint) storedUintMapping;

  // index 7
  mapping (address => DeviceData) storedStructMapping;

  // index 8
  uint[] stroedUintArray;

  // index 9
  DeviceData[] stroedStructArray;

  // index 10
  // index: 000000000000000000000000000000000000000000000000000000000000000a; not 10
  bytes long_bytes;

  struct DeviceData {
   	string deviceBrand;
	string deviceYear;
	string batteryWearLevel;
  }

  constructor() {
  }
}
'''

# TODO: split stamina contract

def run() -> None:
    # get Byzantium VM
    chain = get_chain(ByzantiumVM)
    _deploy_stamina(chain)

def _deploy_stamina(chain: MiningChain) -> None:
    compiled_sol = compile_source(contract_source_code) # Compiled source code
    contract_interface = compiled_sol['<stdin>:StorageTest']

    # Instantiate and deploy contract
    StorageTest = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

    # Build transaction to deploy the contract
    w3_tx = StorageTest.constructor().buildTransaction(W3_TX_DEFAULTS)
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

if __name__ == '__main__':
    run()
