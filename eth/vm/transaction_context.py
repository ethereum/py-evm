import itertools
from typing import (
    Optional,
    Sequence,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth.abc import (
    TransactionContextAPI,
)
from eth.validation import (
    validate_canonical_address,
    validate_uint256,
)


class BaseTransactionContext(TransactionContextAPI):
    __slots__ = ["_gas_price", "_origin", "_log_counter", "_blob_versioned_hashes"]

    def __init__(
        self,
        gas_price: int,
        origin: Address,
        blob_versioned_hashes: Optional[Sequence[Hash32]] = None,
    ) -> None:
        validate_uint256(gas_price, title="TransactionContext.gas_price")
        self._gas_price = gas_price
        validate_canonical_address(origin, title="TransactionContext.origin")
        self._origin = origin
        self._log_counter = itertools.count()

        # post-cancun
        self._blob_versioned_hashes = blob_versioned_hashes or []

    def get_next_log_counter(self) -> int:
        return next(self._log_counter)

    @property
    def gas_price(self) -> int:
        return self._gas_price

    @property
    def origin(self) -> Address:
        return self._origin

    @property
    def blob_versioned_hashes(self) -> Sequence[Hash32]:
        raise NotImplementedError("Not implemented until Cancun.")
