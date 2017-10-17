
import rlp

from eth_keys import keys
from eth_keys.exceptions import (
    BadSignature,
)

from evm.exceptions import (
    ValidationError,
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
    message = transaction.get_message_for_signing()
    try:
        public_key = signature.recover_public_key_from_msg(message)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))

    if not signature.verify_msg(message, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction):
    v, r, s = transaction.v, transaction.r, transaction.s

    canonical_v = v - 27
    vrs = (canonical_v, r, s)
    signature = keys.Signature(vrs=vrs)
    message = transaction.get_message_for_signing()
    public_key = signature.recover_public_key_from_msg(message)
    sender = public_key.to_canonical_address()
    return sender
