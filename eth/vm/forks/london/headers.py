from typing import (
    Any,
    Callable,
    List,
    Optional,
)

from eth_utils import (
    ValidationError,
)
from toolz.functoolz import curry

from eth._utils.headers import (
    compute_gas_limit,
    fill_header_params_from_parent,
    new_timestamp_from_parent,
)
from eth.abc import (
    BlockHeaderAPI,
    BlockHeaderSedesAPI,
)
from eth.constants import GENESIS_GAS_LIMIT
from eth.rlp.headers import BlockHeader
from eth.vm.forks.berlin.headers import (
    compute_berlin_difficulty,
    configure_header,
)

from .blocks import LondonBlockHeader
from .constants import (
    BASE_FEE_MAX_CHANGE_DENOMINATOR,
    ELASTICITY_MULTIPLIER,
    INITIAL_BASE_FEE,
)


def calculate_expected_base_fee_per_gas(parent_header: BlockHeaderAPI) -> int:
    if parent_header is None:
        # Parent is empty when making the genesis header
        return INITIAL_BASE_FEE
    else:
        try:
            parent_base_fee_per_gas = parent_header.base_fee_per_gas
        except AttributeError:
            # Parent is a non-London header
            return INITIAL_BASE_FEE

    # Parent *is* a London header
    parent_gas_target = parent_header.gas_limit // ELASTICITY_MULTIPLIER
    parent_gas_used = parent_header.gas_used

    if parent_gas_used == parent_gas_target:
        return parent_base_fee_per_gas

    elif parent_gas_used > parent_gas_target:
        gas_used_delta = parent_gas_used - parent_gas_target
        overburnt_wei = parent_base_fee_per_gas * gas_used_delta
        base_fee_per_gas_delta = max(
            overburnt_wei // parent_gas_target // BASE_FEE_MAX_CHANGE_DENOMINATOR,
            1,
        )
        return parent_base_fee_per_gas + base_fee_per_gas_delta

    else:
        gas_used_delta = parent_gas_target - parent_gas_used
        underburnt_wei = parent_base_fee_per_gas * gas_used_delta
        base_fee_per_gas_delta = (
            underburnt_wei
            // parent_gas_target
            // BASE_FEE_MAX_CHANGE_DENOMINATOR
        )
        return max(parent_base_fee_per_gas - base_fee_per_gas_delta, 0)


@curry
def create_header_from_parent(difficulty_fn: Callable[[BlockHeaderAPI, int], int],
                              parent_header: Optional[BlockHeaderAPI],
                              **header_params: Any) -> BlockHeaderAPI:

    if 'gas_limit' not in header_params:
        if parent_header is not None and not hasattr(parent_header, 'base_fee_per_gas'):
            # If the previous block was not a London block,
            #   double the gas limit, so the new target is the old gas limit
            header_params['gas_limit'] = parent_header.gas_limit * ELASTICITY_MULTIPLIER
        else:
            # frontier rules
            header_params['gas_limit'] = compute_gas_limit(
                parent_header,
                genesis_gas_limit=GENESIS_GAS_LIMIT,
            )

    # byzantium
    if 'timestamp' not in header_params:
        header_params['timestamp'] = new_timestamp_from_parent(parent_header)

    if 'difficulty' not in header_params:
        if parent_header is None:
            raise ValueError(
                "Must set difficulty when creating a new genesis header (no parent)."
                " Consider 1 for easy mining or eth.constants.GENESIS_DIFFICULTY for consistency."
            )
        else:
            header_params['difficulty'] = difficulty_fn(
                parent_header,
                header_params['timestamp'],
            )

    all_fields = fill_header_params_from_parent(parent_header, **header_params)

    # must add the new field *after* filling, because the general fill function doesn't recognize it
    base_fee_per_gas = calculate_expected_base_fee_per_gas(parent_header)
    if 'base_fee_per_gas' in header_params and all_fields['base_fee_per_gas'] != base_fee_per_gas:
        raise ValidationError(
            f"Cannot select an invalid base_fee_per_gas of:"
            f" {all_fields['base_fee_per_gas']!r}, expected: {base_fee_per_gas}"
        )
    else:
        all_fields['base_fee_per_gas'] = base_fee_per_gas

    new_header = LondonBlockHeader(**all_fields)  # type:ignore
    return new_header


compute_london_difficulty = compute_berlin_difficulty

create_london_header_from_parent = create_header_from_parent(
    compute_london_difficulty
)

configure_london_header = configure_header(compute_london_difficulty)


class LondonBackwardsHeader(BlockHeaderSedesAPI):
    """
    An rlp sedes class for block headers.

    It can serialize and deserialize *both* London and pre-London headers.
    """

    @classmethod
    def serialize(cls, obj: BlockHeaderAPI) -> List[bytes]:
        if isinstance(obj, LondonBlockHeader):
            return LondonBlockHeader.serialize(obj)
        else:
            return BlockHeader.serialize(obj)

    @classmethod
    def deserialize(cls, encoded: List[bytes]) -> BlockHeaderAPI:
        num_fields = len(encoded)
        if num_fields == 16:
            return LondonBlockHeader.deserialize(encoded)
        elif num_fields == 15:
            return BlockHeader.deserialize(encoded)
        else:
            raise ValueError(
                "London & earlier can only handle headers of 15 or 16 fields. "
                f"Got {num_fields} in {encoded!r}"
            )
