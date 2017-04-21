import rlp

from evm.exceptions import (
    InvalidSignature,
)

from evm.utils.address import (
    public_key_to_address,
)
from evm.utils.ecdsa import (
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
    public_key = ecdsa_recover(msg, signature)
    if not ecdsa_verify(msg, signature, public_key):
        raise InvalidSignature("Invalide Signature")


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
