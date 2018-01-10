import json
import os

from evm.utils.hexadecimal import (
    decode_hex,
)

from evm.vm.forks.sharding.config import (
    get_sharding_config,
)


GAS_PRICE = get_sharding_config()['GAS_PRICE']


def get_vmc_json():
    mydir = os.path.dirname(__file__)
    vmc_path = os.path.join(mydir, 'contracts/validator_manager.json')
    vmc_json_str = open(vmc_path).read()
    return json.loads(vmc_json_str)


def create_vmc_tx(TransactionClass, gasprice=GAS_PRICE):
    vmc_json = get_vmc_json()
    vmc_bytecode = decode_hex(vmc_json['bytecode'])
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    return TransactionClass(0, gasprice, 3000000, b'', 0, vmc_bytecode, v, r, s)
