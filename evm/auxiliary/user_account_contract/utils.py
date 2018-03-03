from evm.utils.numeric import (
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)


def assemble_data_field(user_account_transaction, include_signature=True):
    if include_signature:
        signature = b"".join([
            pad32(int_to_big_endian(user_account_transaction.v)),
            pad32(int_to_big_endian(user_account_transaction.r)),
            pad32(int_to_big_endian(user_account_transaction.s)),
        ])
    else:
        signature = b""

    return b''.join([
        signature,
        pad32(int_to_big_endian(user_account_transaction.nonce)),
        pad32(int_to_big_endian(user_account_transaction.gas_price)),
        pad32(int_to_big_endian(user_account_transaction.value)),
        pad32(int_to_big_endian(user_account_transaction.min_block)),
        pad32(int_to_big_endian(user_account_transaction.max_block)),
        pad32(user_account_transaction.destination),
        user_account_transaction.msg_data,
    ])


def get_message_for_signing(user_account_transaction):
    data = assemble_data_field(user_account_transaction, include_signature=False)
    return b"".join([
        data,  # does not include the signature
        user_account_transaction.sig_hash,
    ])
