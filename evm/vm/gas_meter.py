import logging
from typing import (
    cast
)

from evm.exceptions import (
    ValidationError,
    OutOfGas,
)
from evm.validation import (
    validate_uint256,
)
from evm.utils.logging import (
    TraceLogger
)


class GasMeter(object):
    start_gas = None  # type: int

    gas_refunded = None  # type: int
    gas_remaining = None  # type: int

    logger = cast(TraceLogger, logging.getLogger('evm.gas.GasMeter'))

    def __init__(self, start_gas: int) -> None:
        validate_uint256(start_gas, title="Start Gas")

        self.start_gas = start_gas

        self.gas_remaining = self.start_gas
        self.gas_refunded = 0

    #
    # Write API
    #
    def consume_gas(self, amount: int, reason: str) -> None:
        if amount < 0:
            raise ValidationError("Gas consumption amount must be positive")

        if amount > self.gas_remaining:
            raise OutOfGas("Out of gas: Needed {0} - Remaining {1} - Reason: {2}".format(
                amount,
                self.gas_remaining,
                reason,
            ))

        self.gas_remaining -= amount

        self.logger.trace(
            'GAS CONSUMPTION: %s - %s -> %s (%s)',
            self.gas_remaining + amount,
            amount,
            self.gas_remaining,
            reason,
        )

    def return_gas(self, amount: int) -> None:
        if amount < 0:
            raise ValidationError("Gas return amount must be positive")

        self.gas_remaining += amount

        self.logger.trace(
            'GAS RETURNED: %s + %s -> %s',
            self.gas_remaining - amount,
            amount,
            self.gas_remaining,
        )

    def refund_gas(self, amount: int) -> None:
        if amount < 0:
            raise ValidationError("Gas refund amount must be positive")

        self.gas_refunded += amount

        self.logger.trace(
            'GAS REFUND: %s + %s -> %s',
            self.gas_refunded - amount,
            amount,
            self.gas_refunded,
        )
