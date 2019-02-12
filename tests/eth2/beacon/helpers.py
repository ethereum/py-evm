from eth_utils import to_tuple

from eth.constants import (
    ZERO_HASH32,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.types.validator_records import (
    ValidatorRecord,
)
from eth2.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG


def mock_validator_record(pubkey,
                          withdrawal_credentials=ZERO_HASH32,
                          randao_commitment=ZERO_HASH32,
                          status_flags=0,
                          is_active=True):
    return ValidatorRecord(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        randao_layers=0,
        activation_epoch=SERENITY_CONFIG.GENESIS_EPOCH if is_active else FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawal_epoch=FAR_FUTURE_EPOCH,
        penalized_epoch=FAR_FUTURE_EPOCH,
        status_flags=status_flags,
    )


@to_tuple
def get_pseudo_chain(length, genesis_block):
    """
    Get a pseudo chain, only slot and parent_root are valid.
    """
    block = genesis_block.copy()
    yield block
    for slot in range(1, length * 3):
        block = genesis_block.copy(
            slot=slot,
            parent_root=block.root
        )
        yield block
