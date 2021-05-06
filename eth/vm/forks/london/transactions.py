from enum import IntEnum
from eth.vm.forks.london.validation import LondonValidatedTransaction
from cached_property import cached_property
from typing import (
    Dict,
    Sequence,
    Tuple,
    Type,
    Union,
)
from eth_keys.datatypes import PrivateKey
from eth_utils.exceptions import ValidationError

from eth.abc import (
    BaseTransactionAPI,
    ReceiptAPI,
    SignedTransactionAPI,
    TransactionDecoderAPI,
)
from eth.rlp.logs import Log
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import SignedTransactionMethods
from eth.rlp.sedes import address
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_ADDRESS_COST_EIP_2930,
    ACCESS_LIST_STORAGE_KEY_COST_EIP_2930,
    ACCESS_LIST_TRANSACTION_TYPE,
)
from eth.vm.forks.berlin.transactions import (
    AccessListPayloadDecoder,
    AccountAccesses,
    BerlinLegacyTransaction,
    BerlinTransactionBuilder,
    BerlinUnsignedLegacyTransaction,
    TypedTransaction,
)
from eth.vm.forks.istanbul.transactions import (
    ISTANBUL_TX_GAS_SCHEDULE,
)

from eth._utils.transactions import (
    calculate_intrinsic_gas,
    extract_transaction_sender,
    validate_transaction_signature,
)

from .constants import (
    BASE_GAS_FEE_TRANSACTION_TYPE,
)

import rlp
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    to_bytes,
)
from rlp.sedes import (
    CountableList,
    big_endian_int,
    binary,
)

from .constants import BASE_GAS_FEE_TRANSACTION_TYPE


class LondonLegacyTransaction(BerlinLegacyTransaction):
    pass


class LondonUnsignedLegacyTransaction(BerlinUnsignedLegacyTransaction):
    pass


class LondonNormalizedTransaction(BaseTransactionAPI):
    """
    A normalized transaction, used for validation purposes
    """
    def __init__(self,
                 signer_address: Address,
                 nonce: int,
                 gas: int,
                 max_priority_fee_per_gas: int,
                 max_fee_per_gas: int,
                 to: Address,
                 value: int,
                 data: bytes,
                 access_list: Sequence[Tuple[Address, Sequence[int]]]):
        self.signer_address = signer_address
        self.nonce = nonce
        self.gas = gas
        self.max_priority_fee_per_gas = max_priority_fee_per_gas
        self.max_fee_per_gas = max_fee_per_gas
        self.to = to
        self.value = value
        self.data = data
        self.access_list = access_list

    # TODO maybe add properties and make the above variables private?
    def as_validated_transaction(
        self,
        effective_gas_price: int,
        priority_fee_per_gas: int
    ) -> LondonValidatedTransaction:
        return LondonValidatedTransaction(
            effective_gas_price,
            priority_fee_per_gas,
            signer_address=self.signer_address,
            nonce=self.nonce,
            gas=self.gas,
            max_priority_fee_per_gas=self.max_priority_fee_per_gas,
            max_fee_per_gas=self.max_fee_per_gas,
            to=self.to,
            value=self.value,
            data=self.data,
            access_list=self.access_list
        )

class UnsignedBaseGasFeeTransaction(rlp.Serializable):
    _type_id = BASE_GAS_FEE_TRANSACTION_TYPE
    fields = [
        ('chain_id', big_endian_int),
        ('nonce', big_endian_int),
        ('max_priority_fee_per_gas', big_endian_int),
        ('max_fee_per_gas', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
        ('access_list', CountableList(AccountAccesses)),
    ]

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self._type_id)

    def get_message_for_signing(self) -> bytes:
        payload = rlp.encode(self)
        return self._type_byte + payload

    def as_signed_transaction(self, private_key: PrivateKey) -> 'TypedTransaction':
        message = self.get_message_for_signing()
        signature = private_key.sign_msg(message)
        y_parity, r, s = signature.vrs

        signed_transaction = BaseGasFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            y_parity,
            r,
            s
        )
        return LondonTypedTransaction(self._type_id, signed_transaction)


class BaseGasFeeTransaction(rlp.Serializable, SignedTransactionMethods, SignedTransactionAPI):
    _type_id = BASE_GAS_FEE_TRANSACTION_TYPE
    fields = [
        ('chain_id', big_endian_int),
        ('nonce', big_endian_int),
        ('max_priority_fee_per_gas', big_endian_int),
        ('max_fee_per_gas', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
        ('access_list', CountableList(AccountAccesses)),
        ('y_parity', big_endian_int),
        ('r', big_endian_int),
        ('s', big_endian_int),
    ]

    @property
    def gas_price(self) -> None:
        # maybe add a warning, or raise an exception instead?
        return None

    def get_sender(self) -> Address:
        return extract_transaction_sender(self)

    def get_message_for_signing(self) -> bytes:
        unsigned = UnsignedBaseGasFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
        )
        payload = rlp.encode(unsigned)
        return self._type_byte + payload

    def check_signature_validity(self) -> None:
        validate_transaction_signature(self)

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self._type_id)

    @cached_property
    def hash(self) -> Hash32:
        raise NotImplementedError("Call hash() on the TypedTransaction instead")

    def get_intrinsic_gas(self) -> int:
        core_gas = calculate_intrinsic_gas(ISTANBUL_TX_GAS_SCHEDULE, self)

        num_addresses = len(self.access_list)
        preload_address_costs = ACCESS_LIST_ADDRESS_COST_EIP_2930 * num_addresses

        num_slots = sum(len(slots) for _, slots in self.access_list)
        preload_slot_costs = ACCESS_LIST_STORAGE_KEY_COST_EIP_2930 * num_slots

        return core_gas + preload_address_costs + preload_slot_costs


    def encode(self) -> bytes:
        return rlp.encode(self)

    def make_receipt(
            self,
            status: bytes,
            gas_used: int,
            log_entries: Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...]) -> ReceiptAPI:

        logs = [
            Log(address, topics, data)
            for address, topics, data
            in log_entries
        ]
        # TypedTransaction is responsible for wrapping this into a TypedReceipt
        return Receipt(
            state_root=status,
            gas_used=gas_used,
            logs=logs,
        )


class BaseGasFeePayloadDecoder(TransactionDecoderAPI):
    @classmethod
    def decode(cls, payload: bytes) -> SignedTransactionAPI:
        return rlp.decode(payload, sedes=BaseGasFeeTransaction)


class LondonTypedTransaction(TypedTransaction):
    decoders: Dict[int, Type[TransactionDecoderAPI]] = {
        ACCESS_LIST_TRANSACTION_TYPE: AccessListPayloadDecoder,
        BASE_GAS_FEE_TRANSACTION_TYPE: BaseGasFeePayloadDecoder,
    }

    def __init__(self, type_id: int, proxy_target: SignedTransactionAPI) -> None:
        super().__init__(type_id, proxy_target)

    @property
    def max_priority_fee_per_gas(self) -> int:
        return self._inner.max_priority_fee_per_gas

    @property
    def max_fee_per_gas(self) -> int:
        return self._inner.max_fee_per_gas


class LondonTransactionBuilder(BerlinTransactionBuilder):
    @classmethod
    def new_unsigned_base_gas_price_transaction(
            cls,
            chain_id: int,
            nonce: int,
            max_priority_fee_per_gas: int,
            max_fee_per_gas: int,
            gas: int,
            to: Address,
            value: int,
            data: bytes,
            access_list: Sequence[Tuple[Address, Sequence[int]]],) -> LondonTypedTransaction:
        transaction = UnsignedBaseGasFeeTransaction(
            chain_id,
            nonce,
            max_priority_fee_per_gas,
            max_fee_per_gas,
            gas,
            to,
            value,
            data,
            access_list,
        )
        return transaction

    @classmethod
    def new_base_gas_price_transaction(
            cls,
            chain_id: int,
            nonce: int,
            max_priority_fee_per_gas: int,
            max_fee_per_gas: int,
            gas: int,
            to: Address,
            value: int,
            data: bytes,
            access_list: Sequence[Tuple[Address, Sequence[int]]],
            y_parity: int,
            r: int,
            s: int) -> LondonTypedTransaction:
        transaction = BaseGasFeeTransaction(
            chain_id,
            nonce,
            max_priority_fee_per_gas,
            max_fee_per_gas,
            gas,
            to,
            value,
            data,
            access_list,
            y_parity,
            r,
            s,
        )
        return LondonTypedTransaction(BASE_GAS_FEE_TRANSACTION_TYPE, transaction)


def normalize_transaction(
        transaction: Union[LondonLegacyTransaction, LondonTypedTransaction]
    ) -> LondonNormalizedTransaction:

    # fields common to all transactions
    fields = {
        "signer_address": transaction.sender,
        "nonce": transaction.nonce,
        "gas": transaction.gas,
        "to": transaction.to,
        "value": transaction.value,
        "data": transaction.data,
        "access_list": [],
    }

    if isinstance(transaction, (LondonLegacyTransaction, LondonTypedTransaction)):
        fields["max_priority_fee_per_gas"] = transaction.gas_price
        fields["max_fee_per_gas"] = transaction.gas_price
        if isinstance(transaction, LondonTypedTransaction):
            fields["access_list"] = transaction.access_list
            if transaction.type_id == BASE_GAS_FEE_TRANSACTION_TYPE:
                fields["max_priority_fee_per_gas"] = transaction.max_priority_fee_per_gas
                fields["max_fee_per_gas"] = transaction.max_fee_per_gas
            elif transaction.type_id != ACCESS_LIST_TRANSACTION_TYPE:
                raise ValidationError(f"Invalid transaction type_id: {transaction.type_id}")

        return LondonNormalizedTransaction(**fields)

    raise ValidationError(f"Invalid transaction type: {type(transaction)}")
