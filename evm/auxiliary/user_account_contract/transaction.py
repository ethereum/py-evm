from eth_keys import keys

from evm.vm.forks.sharding.transactions import (
    ShardingTransaction,
)

from evm.validation import (
    validate_uint256,
    validate_canonical_address,
    validate_is_bytes,
)

from evm.utils.transactions import (
    V_OFFSET,
)
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from evm.utils.padding import (
    pad32,
)

from .contract import (
    CALLDATA_SIGNATURE,
    CALLDATA_V,
    CALLDATA_R,
    CALLDATA_S,
    CALLDATA_NONCE,
    CALLDATA_GASPRICE,
    CALLDATA_VALUE,
    CALLDATA_MIN_BLOCK,
    CALLDATA_MAX_BLOCK,
    CALLDATA_DESTINATION,
    CALLDATA_DATA,
)


def slice32(start):
    return slice(start, start + 32)


SIGNATURE_SLICE = slice(CALLDATA_SIGNATURE, CALLDATA_SIGNATURE + 96)
SIGNATURE_V_SLICE = slice32(CALLDATA_V)
SIGNATURE_R_SLICE = slice32(CALLDATA_R)
SIGNATURE_S_SLICE = slice32(CALLDATA_S)
NONCE_SLICE = slice32(CALLDATA_NONCE)
GASPRICE_SLICE = slice32(CALLDATA_GASPRICE)
VALUE_SLICE = slice32(CALLDATA_VALUE)
MIN_BLOCK_SLICE = slice32(CALLDATA_MIN_BLOCK)
MAX_BLOCK_SLICE = slice32(CALLDATA_MAX_BLOCK)
DESTINATION_SLICE = slice32(CALLDATA_DESTINATION)
DATA_SLICE = slice(CALLDATA_DATA, None)  # open ended

EMPTY_DATA = b'\x00' * DESTINATION_SLICE.stop


class ForwardingTransaction(ShardingTransaction):
    """A transaction calling the standard user account contract which forwards the call."""

    def __init__(
        self,
        chain_id,
        shard_id,
        to,
        gas,
        access_list,
        destination,
        value,
        nonce,
        min_block,
        max_block,
        gas_price,
        msg_data
    ):
        super().__init__(
            chain_id=chain_id,
            shard_id=shard_id,
            to=to,
            data=EMPTY_DATA,
            gas=gas,
            gas_price=gas_price,
            access_list=access_list,
            code=b'',
        )
        self.destination = destination
        self.value = value
        self.min_block = min_block
        self.max_block = max_block
        self.nonce = nonce
        self.int_gas_price = gas_price
        self.msg_data = msg_data

    #
    # Properties for fields encoded in data
    #

    @property
    def vrs(self):
        v = big_endian_to_int(self.data[SIGNATURE_V_SLICE])
        r = big_endian_to_int(self.data[SIGNATURE_R_SLICE])
        s = big_endian_to_int(self.data[SIGNATURE_S_SLICE])
        return (v, r, s)

    @vrs.setter
    def vrs(self, value):
        for i in value:
            validate_uint256(i)

        b = b''.join([
            pad32(int_to_big_endian(i)) for i in value
        ])

        self.data = self.data[:SIGNATURE_SLICE.start] + b + self.data[SIGNATURE_SLICE.stop:]

    @property
    def nonce(self):
        return big_endian_to_int(self.data[NONCE_SLICE])

    @nonce.setter
    def nonce(self, value):
        validate_uint256(value)
        b = pad32(int_to_big_endian(value))
        self.data = self.data[:NONCE_SLICE.start] + b + self.data[NONCE_SLICE.stop:]

    @property
    def min_block(self):
        return big_endian_to_int(self.data[MIN_BLOCK_SLICE])

    @min_block.setter
    def min_block(self, value):
        validate_uint256(value)
        b = pad32(int_to_big_endian(value))
        self.data = self.data[:MIN_BLOCK_SLICE.start] + b + self.data[MIN_BLOCK_SLICE.stop:]

    @property
    def max_block(self):
        return big_endian_to_int(self.data[MAX_BLOCK_SLICE])

    @max_block.setter
    def max_block(self, value):
        validate_uint256(value)
        b = pad32(int_to_big_endian(value))
        self.data = self.data[:MAX_BLOCK_SLICE.start] + b + self.data[MAX_BLOCK_SLICE.stop:]

    # TODO: rename to gas_price once gas price is removed from ShardingTransaction
    @property
    def int_gas_price(self):
        return big_endian_to_int(self.data[GASPRICE_SLICE])

    @int_gas_price.setter
    def int_gas_price(self, value):
        validate_uint256(value)
        b = pad32(int_to_big_endian(value))
        self.data = self.data[:GASPRICE_SLICE.start] + b + self.data[GASPRICE_SLICE.stop:]

    @property
    def value(self):
        return big_endian_to_int(self.data[VALUE_SLICE])

    @value.setter
    def value(self, value_):
        validate_uint256(value_)
        b = pad32(int_to_big_endian(value_))
        self.data = self.data[:VALUE_SLICE.start] + b + self.data[VALUE_SLICE.stop:]

    @property
    def destination(self):
        destination_padded = self.data[DESTINATION_SLICE]
        assert destination_padded.startswith(b'\x00' * 12)
        return destination_padded[12:]

    @destination.setter
    def destination(self, value):
        validate_canonical_address(value)
        b = pad32(value)
        self.data = self.data[:DESTINATION_SLICE.start] + b + self.data[DESTINATION_SLICE.stop:]

    @property
    def msg_data(self):
        return self.data[DATA_SLICE]

    @msg_data.setter
    def msg_data(self, value):
        validate_is_bytes(value)
        self.data = self.data[:DATA_SLICE.start] + value

    #
    # Signing
    #

    @property
    def is_signed(self):
        return self.vrs != (0, 0, 0)

    def get_message_for_signing(self):
        return b''.join([
            self.data[SIGNATURE_SLICE.stop:],
            self.sig_hash,
        ])

    def sign(self, private_key):
        signature = private_key.sign_msg(self.get_message_for_signing())
        self.vrs = (signature.v + V_OFFSET, signature.r, signature.s)
        return self

    def get_sender(self):
        signature = keys.Signature(vrs=(self.vrs[0] - V_OFFSET, self.vrs[1], self.vrs[2]))
        public_key = signature.recover_public_key_from_msg(self.get_message_for_signing())
        return public_key.to_canonical_address()
