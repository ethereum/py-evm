from cytoolz import (
    compose,
)
from eth_utils import (
    combine_argument_formatters,
    encode_hex,
    int_to_big_endian,
    to_checksum_address,
)
import cytoolz.curried
import eth_utils.curried


int_to_hex = compose(encode_hex, int_to_big_endian)

environment_formatter = eth_utils.curried.apply_formatters_to_dict({
    "currentCoinbase": to_checksum_address,
    "currentDifficulty": int_to_hex,
    "currentGasLimit": int_to_hex,
    "currentNumber": int_to_hex,
    "currentTimestamp": int_to_hex,
    "previousHash": encode_hex,
})


storage_item_formatter = combine_argument_formatters(int_to_hex, int_to_hex)
storage_formatter = cytoolz.curried.itemmap(storage_item_formatter)


account_state_formatter = eth_utils.curried.apply_formatters_to_dict({
    "balance": int_to_hex,
    "nonce": int_to_hex,
    "code": encode_hex,
    "storage": storage_formatter,
})


state_item_formatter = combine_argument_formatters(to_checksum_address, account_state_formatter)
state_formatter = cytoolz.curried.itemmap(state_item_formatter)


access_list_formatter = eth_utils.curried.apply_formatter_to_array(encode_hex)

transaction_group_formatter = eth_utils.curried.apply_formatters_to_dict({
    # all transaction types
    "to": to_checksum_address,
    "data": eth_utils.curried.apply_formatter_to_array(encode_hex),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(int_to_hex),
    "gasPrice": int_to_hex,

    # only main chain transactions
    "nonce": int_to_hex,
    "secretKey": encode_hex,
    "value": eth_utils.curried.apply_formatter_to_array(int_to_hex),

    # only sharding transactions
    "chain_id": int_to_hex,
    "shard_id": int_to_hex,
    "code": encode_hex,
    "access_list": access_list_formatter,
})


execution_formatter = eth_utils.curried.apply_formatters_to_dict({
    "address": to_checksum_address,
    "origin": to_checksum_address,
    "caller": to_checksum_address,
    "code": encode_hex,
    "value": int_to_hex,
    "data": encode_hex,
    "gasPrice": int_to_hex,
    "gas": int_to_hex,
})


expect_element_formatter = eth_utils.curried.apply_formatters_to_dict({
    "result": state_formatter
})
expect_formatter = eth_utils.curried.apply_formatter_to_array(expect_element_formatter)


test_formatter = eth_utils.curried.apply_formatters_to_dict({
    "env": environment_formatter,
    "pre": state_formatter,
    "transaction": transaction_group_formatter,
    "expect": expect_formatter,
    "exec": execution_formatter,
})
filler_formatter = cytoolz.curried.valmap(test_formatter)


state_post_formatter = eth_utils.curried.apply_formatters_to_dict({
    "hash": encode_hex
})


filled_state_test_formatter = cytoolz.curried.valmap(eth_utils.curried.apply_formatters_to_dict({
    "env": environment_formatter,
    "pre": state_formatter,
    "transaction": transaction_group_formatter,
    "post": state_post_formatter,
}))

call_create_item_formatter = eth_utils.curried.apply_formatters_to_dict({
    "data": encode_hex,
    "destination": to_checksum_address,
    "gasLimit": int_to_hex,
    "value": int_to_hex,
})
call_creates_formatter = eth_utils.curried.apply_formatter_to_array(call_create_item_formatter)

filled_vm_test_formatter = cytoolz.curried.valmap(eth_utils.curried.apply_formatters_to_dict({
    "env": environment_formatter,
    "pre": state_formatter,
    "exec": execution_formatter,
    "post": state_formatter,
    "callcreates": call_creates_formatter,
    "logs": encode_hex,
    "gas": int_to_hex,
    "output": encode_hex,
}))
