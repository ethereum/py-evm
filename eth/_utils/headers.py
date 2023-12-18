import datetime
from typing import (
    Dict,
    Optional,
    Tuple,
)

from eth_typing import (
    Address,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    BLANK_ROOT_HASH,
    GAS_LIMIT_ADJUSTMENT_FACTOR,
    GAS_LIMIT_EMA_DENOMINATOR,
    GAS_LIMIT_MAXIMUM,
    GAS_LIMIT_MINIMUM,
    GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR,
    GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR,
    GENESIS_BLOCK_NUMBER,
    GENESIS_PARENT_HASH,
    ZERO_ADDRESS,
)
from eth.typing import (
    BlockNumber,
    HeaderParams,
)


def eth_now() -> int:
    """
    The timestamp is in UTC.
    """
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def new_timestamp_from_parent(parent: Optional[BlockHeaderAPI]) -> int:
    """
    Generate a timestamp to use on a new header.

    Generally, attempt to use the current time. If timestamp is too old (equal
    or less than parent), return `parent.timestamp + 1`. If parent is None,
    then consider this a genesis block.
    """
    if parent is None:
        return eth_now()
    else:
        # header timestamps must increment
        return max(
            parent.timestamp + 1,
            eth_now(),
        )


def fill_header_params_from_parent(
    parent: BlockHeaderAPI,
    gas_limit: int,
    difficulty: int,
    timestamp: int,
    coinbase: Address = ZERO_ADDRESS,
    nonce: Optional[bytes] = None,
    extra_data: Optional[bytes] = None,
    transaction_root: Optional[bytes] = None,
    state_root: Optional[bytes] = None,
    mix_hash: Optional[bytes] = None,
    receipt_root: Optional[bytes] = None,
) -> Dict[str, HeaderParams]:
    if parent is None:
        parent_hash = GENESIS_PARENT_HASH
        block_number = GENESIS_BLOCK_NUMBER
        if state_root is None:
            state_root = BLANK_ROOT_HASH
    else:
        parent_hash = parent.hash
        block_number = BlockNumber(parent.block_number + 1)

        if state_root is None:
            state_root = parent.state_root

    header_kwargs: Dict[str, HeaderParams] = {
        "parent_hash": parent_hash,
        "coinbase": coinbase,
        "state_root": state_root,
        "gas_limit": gas_limit,
        "difficulty": difficulty,
        "block_number": block_number,
        "timestamp": timestamp,
    }
    if nonce is not None:
        header_kwargs["nonce"] = nonce
    if extra_data is not None:
        header_kwargs["extra_data"] = extra_data
    if transaction_root is not None:
        header_kwargs["transaction_root"] = transaction_root
    if receipt_root is not None:
        header_kwargs["receipt_root"] = receipt_root
    if mix_hash is not None:
        header_kwargs["mix_hash"] = mix_hash

    return header_kwargs


def compute_gas_limit_bounds(previous_limit: int) -> Tuple[int, int]:
    """
    Compute the boundaries for the block gas limit based on the parent block.
    """
    boundary_range = previous_limit // GAS_LIMIT_ADJUSTMENT_FACTOR

    # the boundary range is the exclusive limit, therefore the inclusive bounds are
    # (boundary_range - 1) and (boundary_range + 1) for upper and lower bounds, respectively  # noqa: E501
    upper_bound_inclusive = min(GAS_LIMIT_MAXIMUM, previous_limit + boundary_range - 1)
    lower_bound_inclusive = max(GAS_LIMIT_MINIMUM, previous_limit - boundary_range + 1)
    return lower_bound_inclusive, upper_bound_inclusive


def compute_gas_limit(parent_header: BlockHeaderAPI, genesis_gas_limit: int) -> int:
    """
    A simple strategy for adjusting the gas limit.

    For each block:

    - decrease by 1/1024th of the gas limit from the previous block
    - increase by 50% of the total gas used by the previous block

    If the value is less than the given `genesis_gas_limit`:

    - increase the gas limit by 1/1024th of the gas limit from the previous block.

    If the value is less than the GAS_LIMIT_MINIMUM:

    - use the GAS_LIMIT_MINIMUM as the new gas limit.
    """
    if genesis_gas_limit < GAS_LIMIT_MINIMUM:
        raise ValueError(
            "The `genesis_gas_limit` value must be greater than the "
            f"GAS_LIMIT_MINIMUM.  Got {genesis_gas_limit}.  Must be greater than "
            f"{GAS_LIMIT_MINIMUM}"
        )

    if parent_header is None:
        return genesis_gas_limit

    decay = parent_header.gas_limit // GAS_LIMIT_EMA_DENOMINATOR

    if parent_header.gas_used:
        usage_increase = (
            (parent_header.gas_used * GAS_LIMIT_USAGE_ADJUSTMENT_NUMERATOR)
            // (GAS_LIMIT_USAGE_ADJUSTMENT_DENOMINATOR)
            // (GAS_LIMIT_EMA_DENOMINATOR)
        )
    else:
        usage_increase = 0

    gas_limit = max(
        GAS_LIMIT_MINIMUM,
        # + 1 because the decay is an exclusive limit we have to remain inside of
        (parent_header.gas_limit - decay + 1) + usage_increase,
    )

    if gas_limit < GAS_LIMIT_MINIMUM:
        return GAS_LIMIT_MINIMUM
    elif gas_limit < genesis_gas_limit:
        # - 1 because the decay is an exclusive limit we have to remain inside of
        return parent_header.gas_limit + decay - 1
    else:
        return gas_limit
