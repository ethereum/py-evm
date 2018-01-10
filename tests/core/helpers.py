import rlp

from eth_utils import decode_hex

from evm.vm.forks.sharding.transactions import ShardingTransaction


def new_transaction(vm, from_, to, amount, private_key, gas_price=10, gas=100000, data=b''):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    nonce = vm.state.read_only_state_db.get_nonce(from_)
    tx = vm.create_unsigned_transaction(
        nonce=nonce, gas_price=gas_price, gas=gas, to=to, value=amount, data=data)
    return tx.as_signed_transaction(private_key)


def new_sharding_transaction(
        tx_initiator,
        data_destination,
        data_value,
        data_msgdata,
        data_vrs,
        code,
        gas=1000000,
        gas_price=10):
    """
    Create and return a sharding transaction. Data will be encoded in the following order

    [destination, value, msg_data, vrs].
    """
    tx_data = rlp.encode([data_destination, data_value, data_msgdata, data_vrs])
    return ShardingTransaction(
        chain_id=1,
        shard_id=1,
        to=tx_initiator,
        data=tx_data,
        gas=gas,
        gas_price=gas_price,
        access_list=[],
        code=decode_hex(code),
    )
