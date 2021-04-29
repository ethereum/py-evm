from eth_utils.exceptions import ValidationError
from eth.vm.forks.london.constants import (
    BASE_FEE_MAX_CHANGE_DENOMINATOR,
    ELASTICITY_MULTIPLIER
)
from typing import Type

from eth.abc import BlockAPI, BlockHeaderAPI
from eth.rlp.blocks import BaseBlock
from eth._utils.db import get_parent_header
from eth.vm.forks.berlin import BerlinVM
from eth.vm.state import BaseState

from .blocks import LondonBlock
from .state import LondonState


class LondonVM(BerlinVM):
    # fork name
    fork = 'london'

    # classes
    block_class: Type[BaseBlock] = LondonBlock
    _state_class: Type[BaseState] = LondonState

    # Methods
    # create_header_from_parent = staticmethod(create_berlin_header_from_parent)  # type: ignore
    # compute_difficulty = staticmethod(compute_berlin_difficulty)    # type: ignore
    # configure_header = configure_berlin_header

    # @staticmethod
    # def make_receipt(
    #         base_header: BlockHeaderAPI,
    #         transaction: SignedTransactionAPI,
    #         computation: ComputationAPI,
    #         state: StateAPI) -> ReceiptAPI:

    #     gas_used = base_header.gas_used + finalize_gas_used(transaction, computation)

    #     if computation.is_error:
    #         status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
    #     else:
    #         status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

    #     return transaction.make_receipt(status_code, gas_used, computation.get_log_entries())

    @staticmethod
    def calculate_expected_base_fee_per_gas(parent_header: BlockHeaderAPI) -> int:
        parent_base_fee_per_gas = parent_header.base_fee_per_gas
        parent_gas_target = parent_header.gas_target
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

        parent_gas_target = parent_header.gas_target

        max_usable_gas = header.gas_target * ELASTICITY_MULTIPLIER
        if header.gas_used > max_usable_gas:
            raise ValidationError(
                f"Block used too much gas: {header.gas_used} "
                f"(max: {max_usable_gas})"
            )

        if header.gas_target > parent_gas_target + (parent_gas_target // 1024):
            raise ValidationError(
                f"Gas target increased too much (from {parent_gas_target} "
                f"to {header.gas_target})"
            )

        if header.gas_target < parent_gas_target - (parent_gas_target // 1024):
            raise ValidationError(
                f"Gas target decreased too much (from {parent_gas_target} "
                f"to {header.gas_target})"
            )

        expected_base_fee_per_gas = LondonVM.calculate_expected_base_fee_per_gas(parent_header)
        if expected_base_fee_per_gas != header.base_fee_per_gas:
            raise ValidationError(
                f"Incorrect base fee per gas (got {header.base_fee_per_gas}"
                f", expected {expected_base_fee_per_gas})"
            )

        # TODO continue validation

    def validate_block(self, block: BlockAPI) -> None:
        header = block.header
        parent_header = get_parent_header(block.header, self.chaindb)
        LondonVM.validate_header(header, parent_header)

        # return super().validate_block(block)
