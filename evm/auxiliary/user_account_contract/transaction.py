from eth_keys import keys

from evm.vm.forks.sharding.transactions import (
    ShardingTransaction,
)

from evm.validation import (
    validate_uint256,
    validate_lt_secpk1n,
    validate_lte,
    validate_gte,
    validate_canonical_address,
    validate_is_bytes,
)

from evm.utils.transactions import (
    V_OFFSET,
)

from .utils import (
    assemble_data_field,
    get_message_for_signing,
)


class UserAccountTransaction(ShardingTransaction):

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
        msg_data,
        v,
        r,
        s,
    ):
        self.destination = destination
        self.value = value
        self.min_block = min_block
        self.max_block = max_block
        self.nonce = nonce
        self.gas_price = gas_price
        self.msg_data = msg_data

        self.v = v
        self.r = r
        self.s = s

        data = assemble_data_field(self, include_signature=True)

        super().__init__(
            chain_id=chain_id,
            shard_id=shard_id,
            to=to,
            data=data,
            gas=gas,
            access_list=access_list,
            code=b'',
            salt=b'\x00' * 32,
        )

    @classmethod
    def create_unsigned_transaction(cls, *args, **kwargs):
        return UnsignedUserAccountTransaction(*args, **kwargs)

    def get_sender(self):
        signature = keys.Signature(vrs=(self.v - V_OFFSET, self.r, self.s))
        message_for_signing = get_message_for_signing(self)
        public_key = signature.recover_public_key_from_msg(message_for_signing)
        return public_key.to_canonical_address()

    def validate(self):
        super().validate()
        validate_uint256(self.gas_price, "Transaction.gas_price")

        validate_canonical_address(self.destination, "Transaction.destination")
        validate_uint256(self.value, "Transaction.value")
        validate_uint256(self.min_block, "Transaction.min_block")
        validate_uint256(self.max_block, "Transaction.max_block")
        validate_uint256(self.nonce, "Transaction.nonce")
        validate_is_bytes(self.msg_data, "Transaction.msg_data")

        validate_uint256(self.v, title="Transaction.v")
        validate_uint256(self.r, title="Transaction.r")
        validate_uint256(self.s, title="Transaction.s")

        validate_lt_secpk1n(self.r, title="Transaction.r")
        validate_gte(self.r, minimum=1, title="Transaction.r")
        validate_lt_secpk1n(self.s, title="Transaction.s")
        validate_gte(self.s, minimum=1, title="Transaction.s")

        validate_gte(self.v, minimum=27, title="Transaction.v")
        validate_lte(self.v, maximum=28, title="Transaction.v")


class UnsignedUserAccountTransaction(ShardingTransaction):

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
        msg_data,
    ):
        self.destination = destination
        self.value = value
        self.min_block = min_block
        self.max_block = max_block
        self.nonce = nonce
        self.gas_price = gas_price
        self.msg_data = msg_data

        # will be used for signing
        data = assemble_data_field(self, include_signature=False)

        super().__init__(
            chain_id=chain_id,
            shard_id=shard_id,
            to=to,
            data=data,
            gas=gas,
            access_list=access_list,
            code=b"",
            salt=b'\x00' * 32,
        )

    def validate(self):
        super().validate()
        validate_uint256(self.gas_price, "Transaction.gas_price")

        validate_canonical_address(self.destination, "Transaction.destination")
        validate_uint256(self.value, "Transaction.value")
        validate_uint256(self.min_block, "Transaction.min_block")
        validate_uint256(self.max_block, "Transaction.max_block")
        validate_uint256(self.nonce, "Transaction.nonce")
        validate_is_bytes(self.msg_data, "Transaction.msg_data")

    def as_signed_transaction(self, private_key):
        signature = private_key.sign_msg(get_message_for_signing(self))
        return UserAccountTransaction(
            chain_id=self.chain_id,
            shard_id=self.shard_id,
            to=self.to,
            gas=self.gas,
            access_list=self.access_list,
            destination=self.destination,
            value=self.value,
            nonce=self.nonce,
            min_block=self.min_block,
            max_block=self.max_block,
            gas_price=self.gas_price,
            msg_data=self.msg_data,
            v=signature.v + V_OFFSET,
            r=signature.r,
            s=signature.s,
        )
