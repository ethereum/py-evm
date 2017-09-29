import itertools

import rlp

from eth_utils import (
    to_list,
)

from eth_keys import keys
from eth_keys.exceptions import (
    BadSignature,
)

from evm.exceptions import (
    ValidationError,
)

from evm.utils.keccak import (
    keccak,
)


def create_transaction_signature(unsigned_txn, private_key):
    signature = private_key.sign_msg(rlp.encode(unsigned_txn))
    canonical_v, r, s = signature.vrs
    v = canonical_v + 27
    return v, r, s


def validate_transaction_signature(transaction):
    v, r, s = transaction.v, transaction.r, transaction.s
    canonical_v = v - 27
    vrs = (canonical_v, r, s)
    signature = keys.Signature(vrs=vrs)
    unsigned_transaction = transaction.as_unsigned_transaction()
    msg_hash = keccak(rlp.encode(unsigned_transaction))
    try:
        public_key = signature.recover_public_key_from_msg_hash(msg_hash)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))

    if not signature.verify_msg_hash(msg_hash, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction):
    v, r, s = transaction.v, transaction.r, transaction.s
    canonical_v = v - 27
    vrs = (canonical_v, r, s)
    signature = keys.Signature(vrs=vrs)
    unsigned_transaction = transaction.as_unsigned_transaction()
    public_key = signature.recover_public_key_from_msg(rlp.encode(unsigned_transaction))
    sender = public_key.to_canonical_address()
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
