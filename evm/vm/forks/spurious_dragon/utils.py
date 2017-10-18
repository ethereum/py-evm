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
    """
    if computation.is_origin_computation and computation.msg.gas_price == 0:
        yield computation.vm.block.header.coinbase

    for beneficiary in sorted(set(computation.accounts_to_delete.values())):
        if computation.error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            if beneficiary == THREE:
                yield beneficiary
            continue
        else:
            yield beneficiary

    if computation.msg.to != constants.CREATE_CONTRACT_ADDRESS:
        if computation.error and computation.is_origin_computation:
            # Special case to account for geth+parity bug
            if computation.msg.to == THREE:
                yield computation.msg.to
        else:
            yield computation.msg.to

    if not computation.is_origin_computation or not computation.error:
        for child in computation.children:
            yield from collect_touched_accounts(child)
