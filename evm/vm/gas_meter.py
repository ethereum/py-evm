import logging

from evm.exceptions import (
    ValidationError,
    OutOfGas,
)
from evm.validation import (
    validate_uint256,
)


class GasMeter(object):
    start_gas = None

    gas_refunded = None
    gas_remaining = None

    logger = logging.getLogger('evm.gas.GasMeter')

    def __init__(self, start_gas):
        validate_uint256(start_gas, title="Start Gas")

        self.start_gas = start_gas

        self.gas_remaining = self.start_gas
        self.gas_refunded = 0

    #
    # Write API
    #
    def consume_gas(self, amount, reason):
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

    def return_gas(self, amount):
        if amount < 0:
            raise ValidationError("Gas return amount must be positive")

        self.gas_remaining += amount

        self.logger.trace(
            'GAS RETURNED: %s + %s -> %s',
            self.gas_remaining - amount,
            amount,
            self.gas_remaining,
        )

    def refund_gas(self, amount):
        if amount < 0:
            raise ValidationError("Gas refund amount must be positive")

        self.gas_refunded += amount

        self.logger.trace(
            'GAS REFUND: %s + %s -> %s',
            self.gas_refunded - amount,
            amount,
            self.gas_refunded,
        )
