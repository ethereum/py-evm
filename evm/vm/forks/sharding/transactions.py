from evm.validation import (
    validate_uint256,
    validate_is_bytes,
    validate_canonical_address,
    validate_transaction_access_list,
)

from evm.rlp.transactions import (
    BaseShardingTransaction,
)


class ShardingTransaction(BaseShardingTransaction):

    def validate(self):
        validate_uint256(self.chain_id, title="Transaction.chain_id")
        validate_uint256(self.shard_id, title="Transaction.shard_id")

        validate_canonical_address(self.target, title="Transaction.target")
        validate_is_bytes(self.data, title="Transaction.data")

        validate_uint256(self.start_gas, title="Transaction.start_gas")
        validate_uint256(self.gas_price, title="Transaction.gas_price")

        validate_transaction_access_list(self.access_list, title="Transaction.access_list")

        validate_is_bytes(self.code, title="Transaction.code")

        super().validate()
