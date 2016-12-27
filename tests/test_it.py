import pytest

from evm.utils.address import (
    canonicalize_address,
)
from evm.utils.encoding import (
    decode_hex,
    encode_hex,
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


from evm import (
    EVM,
    execute_vm,
)


def test_it():
    evm = EVM()

    for hex_account, account_data in FIXTURE['pre'].items():
        account = canonicalize_address(hex_account)
        for slot, value in account_data['storage'].items():
            evm.set_storage(account, slot, decode_hex(value))
        evm.set_nonce(account, decode_hex(account_data['nonce']))
        evm.set_code(account, decode_hex(account_data['code']))
        evm.set_balance(account, decode_hex(account_data['balance']))

    execute_params = FIXTURE['exec']

    result_evm = execute_vm(
        evm,
        origin=canonicalize_address(execute_params['origin']),
        account=canonicalize_address(execute_params['address']),
        sender=canonicalize_address(execute_params['caller']),
        value=int(execute_params['value'], 16),
        data=decode_hex(execute_params['data']),
        gas=int(execute_params['gas'], 16),
        gas_price=int(execute_params['gasPrice'], 16),
    )

    for account_hex, account_data in FIXTURE['post'].items():
        account = canonicalize_address(account)
        for slot, expected_storage_value in account_data['storage'].items():
            actual_storage_value = encode_hex(
                result_evm.get_storage(account, decode_hex(slot))
            )
            assert actual_storage_value == expected_storage_value
        assert result_evm.get_nonce(account) == decode_hex(account_data['nonce'])
        assert result_evm.get_code(account) == decode_hex(account_data['code'])
        assert result_evm.get_balance(account) == decode_hex(account_data['balance'])
