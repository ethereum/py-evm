from cytoolz import (
    curry,
)


@curry
def execute_plus_buffer(multiplier, state, transaction):
    computation = state.execute_transaction(transaction)

    if computation.is_error:
        raise computation._error

    gas_used = transaction.gas_used_by(computation)

    gas_plus_buffer = int(gas_used * multiplier)

    return min(gas_plus_buffer, state.gas_limit)


double_execution_cost = execute_plus_buffer(2)
