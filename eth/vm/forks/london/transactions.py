from cached_property import cached_property
from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
    Tuple,
    Type,
    overload,
)
from eth_keys.datatypes import PrivateKey
from eth_utils.exceptions import ValidationError

from eth.abc import (
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
from eth.vm.spoof import (
    SpoofTransaction,
)

from eth._utils.transactions import (
    calculate_intrinsic_gas,
    create_transaction_signature,
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
    def as_signed_transaction(self,
                              private_key: PrivateKey,
                              chain_id: int = None) -> LondonLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return LondonLegacyTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
            v=v,
            r=r,
            s=s,
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
        self.max_priority_fee_per_gas = self._inner.max_priority_fee_per_gas
        self.max_fee_per_gas = self._inner.max_fee_per_gas

    # @property
    # def max_priority_fee_per_gas(self) -> int:
    #     return self._inner.max_priority_fee_per_gas

    # @property
    # def max_fee_per_gas(self) -> int:
    #     return self._inner.max_fee_per_gas


class LondonTransactionBuilder(BerlinTransactionBuilder):
    legacy_signed = LondonLegacyTransaction
    legacy_unsigned = LondonUnsignedLegacyTransaction

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
    transaction: SignedTransactionAPI
) -> SignedTransactionAPI:
    if isinstance(transaction, (LondonLegacyTransaction, SpoofTransaction)):
        transaction.max_priority_fee_per_gas = transaction.gas_price
        transaction.max_fee_per_gas = transaction.gas_price
    elif isinstance(transaction, LondonTypedTransaction):
        if transaction.type_id == ACCESS_LIST_TRANSACTION_TYPE:
            transaction.max_priority_fee_per_gas = transaction.gas_price
            transaction.max_fee_per_gas = transaction.gas_price
        elif transaction.type_id != BASE_GAS_FEE_TRANSACTION_TYPE:
            raise ValidationError(f"Invalid transaction type_id: {transaction.type_id}")
    else:
        raise ValidationError(f"Invalid transaction type: {type(transaction)}")

    return transaction