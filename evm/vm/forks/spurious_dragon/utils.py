from eth_utils import to_set

from evm import constants
from evm.utils.address import (
    force_bytes_to_address,
)


THREE = force_bytes_to_address(b'\x03')


@to_set
def collect_touched_accounts(computation):
    """
    Collect all of the accounts that *may* need to be deleted based on EIP161:

    https://github.com/ethereum/EIPs/blob/master/EIPS/eip-161.md

    also see: https://github.com/ethereum/EIPs/issues/716
    """
    if computation.is_origin_computation and computation.transaction_context.gas_price == 0:
        yield computation.vm_state.coinbase

    for beneficiary in sorted(set(computation.accounts_to_delete.values())):
        if computation.is_error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            # https://github.com/ethereum/EIPs/issues/716
            if beneficiary == THREE:
                yield beneficiary
            continue
        else:
            yield beneficiary

    if computation.msg.to != constants.CREATE_CONTRACT_ADDRESS:
        if computation.is_error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            # https://github.com/ethereum/EIPs/issues/716
            if computation.msg.to == THREE:
                yield computation.msg.to
        else:
            yield computation.msg.to

    if not computation.is_origin_computation or not computation.is_error:
        for child in computation.children:
            yield from collect_touched_accounts(child)
