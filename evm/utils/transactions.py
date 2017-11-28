
import rlp

from eth_keys import keys
from eth_keys.exceptions import (
    BadSignature,
)

from evm.exceptions import (
    ValidationError,
)
from evm.utils.numeric import (
    is_even,
    int_to_big_endian,
)


EIP155_CHAIN_ID_OFFSET = 35
V_OFFSET = 27


def is_eip_155_signed_transaction(transaction):
    if transaction.v >= EIP155_CHAIN_ID_OFFSET:
        return True
    else:
        return False


def extract_chain_id(v):
    if is_even(v):
        return (v - EIP155_CHAIN_ID_OFFSET - 1) // 2
    else:
        return (v - EIP155_CHAIN_ID_OFFSET) // 2


def extract_signature_v(v):
    if is_even(v):
        return V_OFFSET + 1
    else:
        return V_OFFSET


def create_transaction_signature(unsigned_txn, private_key, chain_id=None):
    transaction_parts = rlp.decode(rlp.encode(unsigned_txn))

    if chain_id:
        transaction_parts_for_signature = (
            transaction_parts + [int_to_big_endian(chain_id), b'', b'']
        )
    else:
        transaction_parts_for_signature = transaction_parts

    message = rlp.encode(transaction_parts_for_signature)
    signature = private_key.sign_msg(message)

    canonical_v, r, s = signature.vrs

    if chain_id:
        v = canonical_v + chain_id * 2 + EIP155_CHAIN_ID_OFFSET
    else:
        v = canonical_v + V_OFFSET

    return v, r, s


def validate_transaction_signature(transaction):
    if is_eip_155_signed_transaction(transaction):
        v = extract_signature_v(transaction.v)
    else:
        v = transaction.v

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
