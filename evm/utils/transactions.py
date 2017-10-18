
import rlp

from eth_keys import keys
from eth_keys.exceptions import (
    BadSignature,
)

from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_gt,
)

from evm.utils.numeric import (
    is_even,
    int_to_big_endian,
)


def create_transaction_signature(unsigned_txn, private_key):
    signature = private_key.sign_msg(rlp.encode(unsigned_txn))
    canonical_v, r, s = signature.vrs
    v = canonical_v + 27
    return v, r, s


def create_eip155_transaction_signature(unsigned_txn, chain_id, private_key):
    transaction_parts = rlp.decode(rlp.encode(unsigned_txn))
    transaction_parts_for_signature = (
        transaction_parts[:-3] + [int_to_big_endian(chain_id), b'', b'']
    )
    message = rlp.encode(transaction_parts_for_signature)

    signature = private_key.sign_msg(message)
    canonical_v, r, s = signature.vrs
    v = canonical_v + 27
    if v == 27:
        eip155_v = chain_id * 2 + 36
    else:
        eip155_v = chain_id * 2 + 35
    return eip155_v, r, s


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


def is_eip_155_signed_transaction(transaction):
    if transaction.v >= 35:
        return True
    else:
        return False


def extract_chain_id(v):
    if is_even(v):
        return (v - 36) // 2
    else:
        return (v - 35) // 2


def extract_signature_v(v):
    if is_even(v):
        return 28
    else:
        return 27


def validate_eip155_transaction_signature(transaction):
    validate_gt(transaction.v, 34, title="Transaction.v")

    v = extract_signature_v(transaction.v)

    canonical_v = v - 27
    vrs = (canonical_v, transaction.r, transaction.s)
    signature = keys.Signature(vrs=vrs)
    message = transaction.get_message_for_signing()

    try:
        public_key = signature.recover_public_key_from_msg(message)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))

    if not signature.verify_msg(message, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction):
    if is_eip_155_signed_transaction(transaction):
        if is_even(transaction.v):
            v = 28
        else:
            v = 27
    else:
        v = transaction.v

    r, s = transaction.r, transaction.s

    canonical_v = v - 27
    vrs = (canonical_v, r, s)
    signature = keys.Signature(vrs=vrs)
    message = transaction.get_message_for_signing()
    public_key = signature.recover_public_key_from_msg(message)
    sender = public_key.to_canonical_address()
    return sender
