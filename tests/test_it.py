import pytest

from eth_utils import (
    to_canonical_address,
    encode_hex,
    decode_hex,
)


FIXTURE = {
    "callcreates" : [
    ],
    "env" : {
        "currentCoinbase" : "2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
        "currentDifficulty" : "0x0100",
        "currentGasLimit" : "0x0f4240",
        "currentNumber" : "0x00",
        "currentTimestamp" : "0x01"
    },
    "exec" : {
        "address" : "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6",
        "caller" : "cd1722f2947def4cf144679da39c4c32bdc35681",
        "code" : "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff01600055",
        "data" : "0x",
        "gas" : "0x0186a0",
        "gasPrice" : "0x5af3107a4000",
        "origin" : "cd1722f2947def4cf144679da39c4c32bdc35681",
        "value" : "0x0de0b6b3a7640000"
    },
    "gas" : "0x013874",
    "logs" : [
    ],
    "out" : "0x",
    "post" : {
        "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6" : {
            "balance" : "0x0de0b6b3a7640000",
            "code" : "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff01600055",
            "nonce" : "0x00",
            "storage" : {
                "0x00" : "0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe"
            }
        }
    },
    "pre" : {
        "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6" : {
            "balance" : "0x0de0b6b3a7640000",
            "code" : "0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff01600055",
            "nonce" : "0x00",
            "storage" : {
            }
        }
    }
}


from evm.utils.numeric import (
    big_endian_to_int,
)
from evm.storage.memory import (
    MemoryStorage,
)
from evm.vm.evm import (
    execute_vm,
)


def test_it():
    storage = MemoryStorage()

    for account_as_hex, account_data in FIXTURE['pre'].items():
        account = to_canonical_address(account_as_hex)
        for slot_as_hex, value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            value = decode_hex(value)

            storage.set_storage(account, slot, value)

        nonce = int(account_data['nonce'], 16)
        code = decode_hex(account_data['code'])
        balance = int(account_data['balance'], 16)

        storage.set_nonce(account, nonce)
        storage.set_code(account, code)
        storage.set_balance(account, balance)

    execute_params = FIXTURE['exec']

    result_storage = execute_vm(
        storage,
        origin=to_canonical_address(execute_params['origin']),
        account=to_canonical_address(execute_params['address']),
        sender=to_canonical_address(execute_params['caller']),
        value=int(execute_params['value'], 16),
        data=decode_hex(execute_params['data']),
        gas=int(execute_params['gas'], 16),
        gas_price=int(execute_params['gasPrice'], 16),
    )

    for account_as_hex, account_data in FIXTURE['post'].items():
        account = to_canonical_address(account_as_hex)
        for slot_as_hex, expected_storage_value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            expected_storage_value = decode_hex(expected_storage_value_as_hex)
            actual_storage_value = result_storage.get_storage(account, slot)

            assert actual_storage_value == expected_storage_value

        expected_nonce = int(account_data['nonce'], 16)
        expected_code = decode_hex(account_data['code'])
        expected_balance = int(account_data['balance'], 16)

        actual_nonce = result_storage.get_nonce(account)
        actual_code = result_storage.get_code(account)
        actual_balance = result_storage.get_balance(account)

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert actual_balance == expected_balance
