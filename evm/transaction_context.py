from evm.validation import (
    validate_canonical_address,
    validate_uint256,
)


class BaseTransactionContext:
    """
    This immutable object houses information that remains constant for the entire context of the VM
    execution.
    """
    _gas_price = None
    _origin = None

    def __init__(self, gas_price, origin):
        validate_uint256(gas_price, title="TransactionContext.gas_price")
        self._gas_price = gas_price
        validate_canonical_address(origin, title="TransactionContext.origin")
        self._origin = origin

    @property
    def gas_price(self):
        return self._gas_price

    @property
    def origin(self):
        return self._origin
