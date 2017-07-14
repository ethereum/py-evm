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

from evm.ecc import (
    get_ecc_backend,
)

from evm.utils.ecdsa import (
    BadSignature,
)
from evm.utils.keccak import (
    keccak,
)
from evm.utils.secp256k1 import (
    encode_raw_public_key,
)


def create_transaction_signature(unsigned_txn, private_key):
    v, r, s = get_ecc_backend().ecdsa_raw_sign(
        keccak(rlp.encode(unsigned_txn)),
        private_key
    )
    return v, r, s


def validate_transaction_signature(transaction):
    vrs = (transaction.v, transaction.r, transaction.s)
    unsigned_transaction = transaction.as_unsigned_transaction()
    msg_hash = keccak(rlp.encode(unsigned_transaction))
    try:
        public_key = get_ecc_backend().ecdsa_raw_recover(msg_hash, vrs)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))

    if not get_ecc_backend().ecdsa_raw_verify(msg_hash, vrs, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction):
    vrs = (transaction.v, transaction.r, transaction.s)
    unsigned_transaction = transaction.as_unsigned_transaction()
    raw_public_key = get_ecc_backend().ecdsa_raw_recover(
        keccak(rlp.encode(unsigned_transaction)),
        vrs,
    )
    public_key = encode_raw_public_key(raw_public_key)
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
