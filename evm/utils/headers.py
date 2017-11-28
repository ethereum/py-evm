from evm.constants import (
    GAS_LIMIT_EMA_DENOMINATOR,
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_MINIMUM,
    GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR,
    GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR,
)


def compute_gas_limit_bounds(parent):
    """
    Compute the boundaries for the block gas limit based on the parent block.
    """
    boundary_range = parent.gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR
    upper_bound = parent.gas_limit + boundary_range
    lower_bound = max(GAS_LIMIT_MINIMUM, parent.gas_limit - boundary_range)
    return lower_bound, upper_bound


def compute_gas_limit(parent_header, gas_limit_floor):
    """
    A simple strategy for adjusting the gas limit.

    For each block:

    - decrease by 1/1024th of the gas limit from the previous block
    - increase by 50% of the total gas used by the previous block

    If the value is less than the given `gas_limit_floor`:

    - increase the gas limit by 1/1024th of the gas limit from the previous block.

    If the value is less than the GAS_LIMIT_MINIMUM:

    - use the GAS_LIMIT_MINIMUM as the new gas limit.
    """
    if gas_limit_floor < GAS_LIMIT_MINIMUM:
        raise ValueError(
            "The `gas_limit_floor` value must be greater than the "
            "GAS_LIMIT_MINIMUM.  Got {0}.  Must be greater than "
            "{1}".format(gas_limit_floor, GAS_LIMIT_MINIMUM)
        )

    decay = parent_header.gas_limit // GAS_LIMIT_EMA_DENOMINATOR

    if parent_header.gas_used:
        usage_increase = (
            parent_header.gas_used * GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR
        ) // (
            GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR
        ) // (
            GAS_LIMIT_EMA_DENOMINATOR
        )
    else:
        usage_increase = 0

    gas_limit = max(
        GAS_LIMIT_MINIMUM,
        parent_header.gas_limit - decay + usage_increase
    )

    if gas_limit < gas_limit_floor:
        return GAS_LIMIT_MINIMUM
    else:
        return gas_limit
