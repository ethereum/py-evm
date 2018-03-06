from evm.constants import (
    GAS_TX,
    GAS_TXCREATE,
    GAS_TXDATAZERO,
    GAS_TXDATANONZERO,
)
from evm.validation import (
    validate_uint256,
    validate_is_bytes,
    validate_transaction_access_list,
    validate_canonical_address,
    validate_word,
)

from evm.rlp.transactions import (
    BaseShardingTransaction,
)


class ShardingTransaction(BaseShardingTransaction):

    def validate(self):
        validate_uint256(self.chain_id, title="Transaction.chain_id")
        validate_uint256(self.shard_id, title="Transaction.shard_id")

        validate_canonical_address(self.to, title="Transaction.to")
        validate_is_bytes(self.data, title="Transaction.data")

        validate_uint256(self.gas, title="Transaction.gas")

        validate_transaction_access_list(self.access_list, title="Transaction.access_list")

        validate_is_bytes(self.code, title="Transaction.code")
        validate_word(self.salt, title="Transaction.salt")

        super(ShardingTransaction, self).validate()

    def get_intrinsic_gas(self):
        return _get_sharding_intrinsic_gas(self.data, self.code)


def _get_sharding_intrinsic_gas(transaction_data, transaction_code):
    num_zero_bytes = transaction_data.count(b'\x00') + transaction_code.count(b'\x00')
    num_non_zero_bytes = len(transaction_data) + len(transaction_code) - num_zero_bytes
    if transaction_code:
        create_cost = GAS_TXCREATE
    else:
        create_cost = 0
    return (
        GAS_TX +
        num_zero_bytes * GAS_TXDATAZERO +
        num_non_zero_bytes * GAS_TXDATANONZERO +
        create_cost
    )
