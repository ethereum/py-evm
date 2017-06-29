import itertools

import rlp

from eth_utils import (
    to_list,
)

from evm.exceptions import (
    ValidationError,
)

from evm.utils.address import (
    public_key_to_address,
)
from evm.utils.ecdsa import (
    BadSignature,
    ecdsa_sign,
    decode_signature,
    encode_signature,
    ecdsa_recover,
    ecdsa_verify,
)


def create_transaction_signature(unsigned_txn, private_key):
    signature = ecdsa_sign(rlp.encode(unsigned_txn), private_key)
    v, r, s = decode_signature(signature)
    return v, r, s


def validate_transaction_signature(transaction):
    signature = encode_signature(
        v=transaction.v,
        r=transaction.r,
        s=transaction.s,
    )
    unsigned_transaction = transaction.as_unsigned_transaction()
    msg = rlp.encode(unsigned_transaction)
    try:
        public_key = ecdsa_recover(msg, signature)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))
    if not ecdsa_verify(msg, signature, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction):
    unsigned_transaction = transaction.as_unsigned_transaction()
    signature = encode_signature(
        v=transaction.v,
        r=transaction.r,
        s=transaction.s,
    )
    public_key = ecdsa_recover(rlp.encode(unsigned_transaction), signature)
    sender = public_key_to_address(public_key)
    return sender


@to_list
def get_transactions_from_db(transaction_db, transaction_class):
    for transaction_idx in itertools.count():
        transaction_key = rlp.encode(transaction_idx)
        if transaction_key in transaction_db:
            transaction_data = transaction_db[transaction_key]
            yield rlp.decode(transaction_data, sedes=transaction_class)
        else:
            break
