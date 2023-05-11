from typing import (
    Iterable,
    Optional,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)

from eth._utils.generator import (
    CachedIterable,
)
from eth.abc import (
    ExecutionContextAPI,
)


class ExecutionContext(ExecutionContextAPI):
    _coinbase = None
    _timestamp = None
    _number = None
    _difficulty = None
    _mix_hash = None
    _gas_limit = None
    _prev_hashes = None
    _chain_id = None
    _base_fee_per_gas = None

    def __init__(
        self,
        coinbase: Address,
        timestamp: int,
        block_number: BlockNumber,
        difficulty: int,
        mix_hash: Hash32,
        gas_limit: int,
        prev_hashes: Iterable[Hash32],
        chain_id: int,
        base_fee_per_gas: Optional[int] = None,
    ) -> None:
        self._coinbase = coinbase
        self._timestamp = timestamp
        self._block_number = block_number
        self._difficulty = difficulty
        self._mix_hash = mix_hash
        self._gas_limit = gas_limit
        self._prev_hashes = CachedIterable(prev_hashes)
        self._chain_id = chain_id
        self._base_fee_per_gas = base_fee_per_gas

    @property
    def coinbase(self) -> Address:
        return self._coinbase

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @property
    def block_number(self) -> BlockNumber:
        return self._block_number

    @property
    def difficulty(self) -> int:
        return self._difficulty

    @property
    def mix_hash(self) -> Hash32:
        return self._mix_hash

    @property
    def gas_limit(self) -> int:
        return self._gas_limit

    @property
    def prev_hashes(self) -> Iterable[Hash32]:
        return self._prev_hashes

    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def base_fee_per_gas(self) -> int:
        if self._base_fee_per_gas is None:
            raise AttributeError(
                f"This header at Block #{self.block_number} "
                "does not have a base gas fee"
            )
        else:
            return self._base_fee_per_gas
