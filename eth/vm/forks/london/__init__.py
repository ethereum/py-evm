from typing import Type

from eth._utils.db import get_parent_header
from eth.abc import BlockAPI, BlockHeaderAPI
from eth_utils.exceptions import ValidationError
from eth.rlp.blocks import BaseBlock
from eth.vm.forks.berlin import BerlinVM
from eth.vm.state import BaseState

from .blocks import LondonBlock
from .constants import (
    BASE_FEE_MAX_CHANGE_DENOMINATOR,
    ELASTICITY_MULTIPLIER
)
from .headers import (
    compute_london_difficulty,
    create_london_header_from_parent,
)
from .state import LondonState


class LondonVM(BerlinVM):
    # fork name
    fork = 'london'

    # classes
    block_class: Type[BaseBlock] = LondonBlock
    _state_class: Type[BaseState] = LondonState

    # Methods
    # skip header validation: validate everything in the executor as we need state access
    validate_transaction_against_header = lambda header, transaction: None  # type: ignore
    create_header_from_parent = staticmethod(create_london_header_from_parent)  # type: ignore
    compute_difficulty = staticmethod(compute_london_difficulty)    # type: ignore
    # configure_header = configure_berlin_header

    @staticmethod
    def calculate_expected_base_fee_per_gas(parent_header: BlockHeaderAPI) -> int:
        parent_base_fee_per_gas = parent_header.base_fee_per_gas
        parent_gas_target = parent_header.gas_limit
        parent_gas_used = parent_header.gas_used

        if parent_gas_used == parent_gas_target:
            return parent_base_fee_per_gas

        elif parent_gas_used > parent_gas_target:
            gas_used_delta = parent_gas_used - parent_base_fee_per_gas
            base_fee_per_gas_delta = max(
                (
                    parent_base_fee_per_gas * gas_used_delta // \
                    parent_gas_target // BASE_FEE_MAX_CHANGE_DENOMINATOR
                ),
                1
            )
            return parent_base_fee_per_gas + base_fee_per_gas_delta

        else:
            gas_used_delta = parent_gas_target - parent_gas_used
            base_fee_per_gas_delta = parent_base_fee_per_gas * gas_used_delta \
                // parent_gas_target // BASE_FEE_MAX_CHANGE_DENOMINATOR
            return max(parent_base_fee_per_gas - base_fee_per_gas_delta, 0)

    @classmethod
    def validate_header(cls,
                        header: BlockHeaderAPI,
                        parent_header: BlockHeaderAPI) -> None:

        header_gas_target = header.gas_limit
        parent_gas_target = parent_header.gas_limit

        max_usable_gas = header_gas_target * ELASTICITY_MULTIPLIER
        if header.gas_used > max_usable_gas:
            raise ValidationError(
                f"Block used too much gas: {header.gas_used} "
                f"(max: {max_usable_gas})"
            )

        if header_gas_target > parent_gas_target + (parent_gas_target // 1024):
            raise ValidationError(
                f"Gas target increased too much (from {parent_gas_target} "
                f"to {header_gas_target})"
            )

        if header_gas_target < parent_gas_target - (parent_gas_target // 1024):
            raise ValidationError(
                f"Gas target decreased too much (from {parent_gas_target} "
                f"to {header_gas_target})"
            )

        expected_base_fee_per_gas = LondonVM.calculate_expected_base_fee_per_gas(parent_header)
        if expected_base_fee_per_gas != header.base_fee_per_gas:
            raise ValidationError(
                f"Incorrect base fee per gas (got {header.base_fee_per_gas}"
                f", expected {expected_base_fee_per_gas})"
            )

    def validate_block(self, block: BlockAPI) -> None:
        header = block.header
        parent_header = get_parent_header(block.header, self.chaindb)
        LondonVM.validate_header(header, parent_header)

        # return super().validate_block(block)
