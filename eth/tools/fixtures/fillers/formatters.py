from typing import (
    Any,
    Callable,
    List,
)

from eth_utils.curried import (
    apply_formatter_to_array,
    apply_formatters_to_dict,
    apply_formatters_to_sequence,
    encode_hex,
    to_checksum_address,
    to_hex,
)
from eth_utils.toolz import (
    curried,
)

environment_formatter = apply_formatters_to_dict(
    {
        "currentCoinbase": to_checksum_address,
        "previousHash": encode_hex,
        "currentNumber": to_hex,
        "currentDifficulty": to_hex,
        "currentGasLimit": to_hex,
        "currentTimestamp": to_hex,
    }
)


storage_item_formatter: Callable[[List[Any]], List[Any]]
storage_item_formatter = apply_formatters_to_sequence([to_hex, to_hex])
storage_formatter = curried.itemmap(storage_item_formatter)


account_state_formatter = apply_formatters_to_dict(
    {
        "balance": to_hex,
        "nonce": to_hex,
        "code": encode_hex,
        "storage": storage_formatter,
    }
)


state_item_formatter: Callable[[List[Any]], List[Any]]
state_item_formatter = apply_formatters_to_sequence(
    [to_checksum_address, account_state_formatter]
)
state_formatter = curried.itemmap(state_item_formatter)


transaction_group_formatter = apply_formatters_to_dict(
    {
        # all transaction types
        "to": to_checksum_address,
        "data": apply_formatter_to_array(encode_hex),
        "gasLimit": apply_formatter_to_array(to_hex),
        "gasPrice": to_hex,
        "nonce": to_hex,
        "secretKey": encode_hex,
        "value": apply_formatter_to_array(to_hex),
    }
)


execution_formatter = apply_formatters_to_dict(
    {
        "address": to_checksum_address,
        "origin": to_checksum_address,
        "caller": to_checksum_address,
        "code": encode_hex,
        "value": to_hex,
        "data": encode_hex,
        "gasPrice": to_hex,
        "gas": to_hex,
    }
)


expect_element_formatter = apply_formatters_to_dict({"result": state_formatter})
expect_formatter: Callable[[List[Any]], List[Any]]
expect_formatter = apply_formatter_to_array(expect_element_formatter)


test_formatter = apply_formatters_to_dict(
    {
        "env": environment_formatter,
        "pre": state_formatter,
        "transaction": transaction_group_formatter,
        "expect": expect_formatter,
        "exec": execution_formatter,
    }
)
filler_formatter = curried.valmap(test_formatter)


state_post_formatter = apply_formatters_to_dict({"hash": encode_hex})


filled_state_test_formatter = curried.valmap(
    apply_formatters_to_dict(
        {
            "env": environment_formatter,
            "pre": state_formatter,
            "transaction": transaction_group_formatter,
            "post": state_post_formatter,
        }
    )
)

call_create_item_formatter = apply_formatters_to_dict(
    {
        "data": encode_hex,
        "destination": to_checksum_address,
        "gasLimit": to_hex,
        "value": to_hex,
    }
)
call_creates_formatter: Callable[[List[Any]], List[Any]]
call_creates_formatter = apply_formatter_to_array(call_create_item_formatter)

filled_vm_test_formatter = curried.valmap(
    apply_formatters_to_dict(
        {
            "env": environment_formatter,
            "pre": state_formatter,
            "exec": execution_formatter,
            "post": state_formatter,
            "callcreates": call_creates_formatter,
            "logs": encode_hex,
            "gas": to_hex,
            "output": encode_hex,
        }
    )
)
