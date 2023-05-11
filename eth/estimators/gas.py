from typing import (
    Optional,
    cast,
)

from eth_utils.toolz import (
    curry,
)

from eth.abc import (
    SignedTransactionAPI,
    StateAPI,
)
from eth.exceptions import (
    VMError,
)
from eth.vm.spoof import (
    SpoofTransaction,
)


def _get_computation_error(
    state: StateAPI, transaction: SignedTransactionAPI
) -> Optional[VMError]:
    snapshot = state.snapshot()

    try:
        computation = state.apply_transaction(transaction)
        if computation.is_error:
            return computation.error
        else:
            return None

    finally:
        state.revert(snapshot)


@curry
def binary_gas_search(
    state: StateAPI, transaction: SignedTransactionAPI, tolerance: int = 1
) -> int:
    """
    Run the transaction with various gas limits, progressively
    approaching the minimum needed to succeed without an OutOfGas exception.

    The starting range of possible estimates is:
    [transaction.intrinsic_gas, state.gas_limit].
    After the first OutOfGas exception, the range is:
        (largest_limit_out_of_gas, state.gas_limit].
    After the first run not out of gas, the range is:
        (largest_limit_out_of_gas, smallest_success].

    :param int tolerance: When the range of estimates is less than tolerance,
        return the top of the range.
    :returns int: The smallest confirmed gas to not throw an OutOfGas exception,
        subject to tolerance. If OutOfGas is thrown at block limit, return block limit.
    :raises VMError: if the computation fails even when given the block gas_limit to
        complete
    """
    if not hasattr(transaction, "sender"):
        raise TypeError(
            "Transaction is missing attribute sender.",
            "If sending an unsigned transaction, use SpoofTransaction and provide the",
            "sender using the 'from' parameter",
        )

    minimum_transaction = cast(
        SignedTransactionAPI,
        SpoofTransaction(
            transaction,
            gas=transaction.intrinsic_gas,
            gas_price=0,
        ),
    )

    if _get_computation_error(state, minimum_transaction) is None:
        return transaction.intrinsic_gas

    maximum_transaction = cast(
        SignedTransactionAPI,
        SpoofTransaction(
            transaction,
            gas=state.gas_limit,
            gas_price=0,
        ),
    )
    error = _get_computation_error(state, maximum_transaction)
    if error is not None:
        raise error

    minimum_viable = state.gas_limit
    maximum_out_of_gas = transaction.intrinsic_gas
    while minimum_viable - maximum_out_of_gas > tolerance:
        midpoint = (minimum_viable + maximum_out_of_gas) // 2
        test_transaction = cast(
            SignedTransactionAPI, SpoofTransaction(transaction, gas=midpoint)
        )
        if _get_computation_error(state, test_transaction) is None:
            minimum_viable = midpoint
        else:
            maximum_out_of_gas = midpoint

    return minimum_viable


# Estimate in increments of intrinsic gas usage
binary_gas_search_intrinsic_tolerance = binary_gas_search(tolerance=21000)

# Estimate in increments of 1000 gas, takes roughly 5 more executions than
# intrinsic to estimate
binary_gas_search_1000_tolerance = binary_gas_search(tolerance=1000)

# Estimate to the exact gas, takes roughly 15 more executions than intrinsic to estimate
binary_gas_search_exact = binary_gas_search(tolerance=1)
