from typing import Iterable

from eth_typing import Address

from eth_utils import to_set

from eth import constants

from eth._utils.address import (
    force_bytes_to_address,
)

from eth.vm.computation import BaseComputation


THREE = force_bytes_to_address(b'\x03')


@to_set
def collect_touched_accounts(computation: BaseComputation) -> Iterable[Address]:
    """
    Collect all of the accounts that *may* need to be deleted based on
    `EIP-161 <https://eips.ethereum.org/EIPS/eip-161>`_.

    Checking whether they *do* need to be deleted happens in the caller.

    See also: https://github.com/ethereum/EIPs/issues/716
    """
    # collect the coinbase account if it was touched via zero-fee transfer
    if computation.is_origin_computation and computation.transaction_context.gas_price == 0:
        yield computation.state.coinbase

    # collect those explicitly marked for deletion ("beneficiary" is of SELFDESTRUCT)
    for beneficiary in sorted(set(computation.accounts_to_delete.values())):
        if computation.is_error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            # https://github.com/ethereum/EIPs/issues/716
            if beneficiary == THREE:
                yield beneficiary
            continue
        else:
            yield beneficiary

    # collect account directly addressed
    if computation.msg.to != constants.CREATE_CONTRACT_ADDRESS:
        if computation.is_error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            # https://github.com/ethereum/EIPs/issues/716
            if computation.msg.to == THREE:
                yield computation.msg.to
        else:
            yield computation.msg.to

    # recurse into nested computations if this one was successful
    if not computation.is_error:
        for child in computation.children:
            yield from collect_touched_accounts(child)
