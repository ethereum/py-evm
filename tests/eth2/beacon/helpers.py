from eth_utils import to_tuple

from eth.constants import (
    ZERO_HASH32,
)

from eth2.configs import Eth2Config
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.types.validator_records import (
    ValidatorRecord,
)


def mock_validator_record(pubkey,
                          config: Eth2Config,
                          withdrawal_credentials=ZERO_HASH32,
                          is_active=True):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_epoch=config.GENESIS_EPOCH if is_active else FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        initiated_exit=False,
        slashed=False,
    )


@to_tuple
def get_pseudo_chain(length, genesis_block):
    """
    Get a pseudo chain, only slot and previous_block_root are valid.
    """
    block = genesis_block.copy()
    yield block
    for slot in range(1, length * 3):
        block = genesis_block.copy(
            slot=slot,
            previous_block_root=block.signing_root
        )
        yield block
