from typing import (
    NamedTuple,
)

from eth_keys import (
    datatypes,
    keys,
)
from eth_keys.exceptions import (
    BadSignature,
)
from eth_utils import (
    ValidationError,
    int_to_big_endian,
)
import rlp

from eth._utils.numeric import (
    is_even,
)
from eth.abc import (
    SignedTransactionAPI,
    UnsignedTransactionAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.rlp.transactions import (
    BaseTransaction,
)
from eth.typing import (
    VRS,
    Address,
)

EIP155_CHAIN_ID_OFFSET = 35
# Add this offset to y_parity to get "v" for legacy transactions, from Frontier
V_OFFSET = 27


def is_eip_155_signed_transaction(transaction: BaseTransaction) -> bool:
    return transaction.v >= EIP155_CHAIN_ID_OFFSET


def extract_chain_id(v: int) -> int:
    if is_even(v):
        return (v - EIP155_CHAIN_ID_OFFSET - 1) // 2
    else:
        return (v - EIP155_CHAIN_ID_OFFSET) // 2


def extract_signature_v(v: int) -> int:
    if is_even(v):
        return V_OFFSET + 1
    else:
        return V_OFFSET


def create_transaction_signature(
    unsigned_txn: UnsignedTransactionAPI,
    private_key: datatypes.PrivateKey,
    chain_id: int = None,
) -> VRS:
    transaction_parts = rlp.decode(rlp.encode(unsigned_txn))

    if chain_id:
        transaction_parts_for_signature = transaction_parts + [
            int_to_big_endian(chain_id),
            b"",
            b"",
        ]
    else:
        transaction_parts_for_signature = transaction_parts

    message = rlp.encode(transaction_parts_for_signature)
    signature = private_key.sign_msg(message)

    canonical_v, r, s = signature.vrs

    if chain_id:
        v = canonical_v + chain_id * 2 + EIP155_CHAIN_ID_OFFSET
    else:
        v = canonical_v + V_OFFSET

    return VRS((v, r, s))


def validate_transaction_signature(transaction: SignedTransactionAPI) -> None:
    message = transaction.get_message_for_signing()
    vrs = (transaction.y_parity, transaction.r, transaction.s)
    try:
        signature = keys.Signature(vrs=vrs)
        public_key = signature.recover_public_key_from_msg(message)
    except BadSignature as e:
        raise ValidationError(f"Bad Signature: {str(e)}")

    if not signature.verify_msg(message, public_key):
        raise ValidationError("Invalid Signature")


def extract_transaction_sender(transaction: SignedTransactionAPI) -> Address:
    vrs = (transaction.y_parity, transaction.r, transaction.s)
    signature = keys.Signature(vrs=vrs)
    message = transaction.get_message_for_signing()
    public_key = signature.recover_public_key_from_msg(message)
    sender = public_key.to_canonical_address()
    return Address(sender)


class IntrinsicGasSchedule(NamedTuple):
    gas_tx: int
    gas_txcreate: int
    gas_txdatazero: int
    gas_txdatanonzero: int


def calculate_intrinsic_gas(
    gas_schedule: IntrinsicGasSchedule,
    transaction: SignedTransactionAPI,
) -> int:
    num_zero_bytes = transaction.data.count(b"\x00")
    num_non_zero_bytes = len(transaction.data) - num_zero_bytes
    if transaction.to == CREATE_CONTRACT_ADDRESS:
        create_cost = gas_schedule.gas_txcreate
    else:
        create_cost = 0
    return (
        gas_schedule.gas_tx
        + num_zero_bytes * gas_schedule.gas_txdatazero
        + num_non_zero_bytes * gas_schedule.gas_txdatanonzero
        + create_cost
    )
