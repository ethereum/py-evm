from typing import Type

from eth_utils.exceptions import ValidationError

from eth.abc import (
    BlockHeaderAPI,
)
from eth.rlp.blocks import BaseBlock
from eth.validation import validate_gas_limit
from eth.vm.forks.berlin import BerlinVM
from eth.vm.state import BaseState

from .blocks import LondonBlock
from .constants import (
    EIP3529_MAX_REFUND_QUOTIENT,
    ELASTICITY_MULTIPLIER,
)
from .headers import (
    calculate_expected_base_fee_per_gas,
    compute_london_difficulty,
    configure_london_header,
    create_london_header_from_parent,
)
from .state import LondonState


class LondonVM(BerlinVM):
    # fork name
    fork = "london"

    # classes
    block_class: Type[BaseBlock] = LondonBlock
    _state_class: Type[BaseState] = LondonState

    # Methods
    create_header_from_parent = staticmethod(  # type: ignore
        create_london_header_from_parent(compute_london_difficulty)
    )
    compute_difficulty = staticmethod(compute_london_difficulty)  # type: ignore
    configure_header = configure_london_header

    @classmethod
    def validate_gas(
        cls, header: BlockHeaderAPI, parent_header: BlockHeaderAPI
    ) -> None:
        if hasattr(parent_header, "base_fee_per_gas"):
            # Follow normal gas limit rules if the previous block had a base fee
            parent_gas_limit = parent_header.gas_limit
        else:
            # On the fork block, double the gas limit.
            # That way, the gas target (which is half the London limit) equals the
            # previous (pre-London) gas limit.
            parent_gas_limit = parent_header.gas_limit * ELASTICITY_MULTIPLIER

        validate_gas_limit(header.gas_limit, parent_gas_limit)

        expected_base_fee_per_gas = calculate_expected_base_fee_per_gas(parent_header)
        if expected_base_fee_per_gas != header.base_fee_per_gas:
            raise ValidationError(
                f"Header has invalid base fee per gas (has {header.base_fee_per_gas}"
                f", expected {expected_base_fee_per_gas})"
            )

    @classmethod
    def calculate_net_gas_refund(cls, consumed_gas: int, gross_refund: int) -> int:
        max_refund = consumed_gas // EIP3529_MAX_REFUND_QUOTIENT
        return min(max_refund, gross_refund)
