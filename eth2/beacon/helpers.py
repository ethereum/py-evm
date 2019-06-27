from typing import (
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_utils import (
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth2._utils.hash import (
    hash_eth2,
)
from eth2.beacon.signature_domain import (
    SignatureDomain,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Slot,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_epoch_for_active_index_root,
    validate_epoch_for_randao_mix,
)
from eth2.configs import (
    CommitteeConfig,
)

from eth2.beacon.types.forks import Fork
from eth2.beacon.types.validators import Validator

if TYPE_CHECKING:
    from eth2.beacon.types.states import BeaconState  # noqa: F401


def slot_to_epoch(slot: Slot, slots_per_epoch: int) -> Epoch:
    return Epoch(slot // slots_per_epoch)


def get_epoch_start_slot(epoch: Epoch, slots_per_epoch: int) -> Slot:
    return Slot(epoch * slots_per_epoch)


def get_active_validator_indices(validators: Sequence[Validator],
                                 epoch: Epoch) -> Tuple[ValidatorIndex, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        ValidatorIndex(index)
        for index, validator in enumerate(validators)
        if validator.is_active(epoch)
    )


def _get_historical_root(
        historical_roots: Sequence[Hash32],
        state_slot: Slot,
        slot: Slot,
        slots_per_historical_root: int) -> Hash32:
    """
    Return the historical root at a recent ``slot``.
    """
    if slot >= state_slot:
        raise ValidationError(
            "slot ({}) should be less than state.slot ({})".format(
                slot,
                state_slot,
            )
        )
    if state_slot > slot + slots_per_historical_root:
        raise ValidationError(
            "state.slot ({}) should be less than or equal to "
            "(slot + slots_per_historical_root) ({}), "
            "where slot={}, slots_per_historical_root={}".format(
                state_slot,
                slot + slots_per_historical_root,
                slot,
                slots_per_historical_root,
            )
        )
    return historical_roots[slot % slots_per_historical_root]


def get_block_root_at_slot(state: 'BeaconState',
                           slot: Slot,
                           slots_per_historical_root: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    return _get_historical_root(
        state.block_roots,
        state.slot,
        slot,
        slots_per_historical_root,
    )


def get_block_root(state: 'BeaconState',
                   epoch: Epoch,
                   slots_per_epoch: int,
                   slots_per_historical_root: int) -> Hash32:
    return get_block_root_at_slot(
        state,
        get_epoch_start_slot(epoch, slots_per_epoch),
        slots_per_historical_root,
    )


def get_randao_mix(state: 'BeaconState',
                   epoch: Epoch,
                   slots_per_epoch: int,
                   epochs_per_historical_vector: int,
                   perform_validation: bool=True) -> Hash32:
    """
    Return the randao mix at a recent ``epoch``.

    NOTE: There is one use of this function (``generate_seed``) where
    the ``epoch`` does not satisfy ``validate_epoch_for_randao_mix`` so
    callers need the flexibility to specify validation.
    """
    if perform_validation:
        validate_epoch_for_randao_mix(
            state.current_epoch(slots_per_epoch),
            epoch,
            epochs_per_historical_vector,
        )

    return state.randao_mixes[epoch % epochs_per_historical_vector]


def get_active_index_root(state: 'BeaconState',
                          epoch: Epoch,
                          slots_per_epoch: int,
                          activation_exit_delay: int,
                          epochs_per_historical_vector: int) -> Hash32:
    """
    Return the index root at a recent ``epoch``.
    """
    validate_epoch_for_active_index_root(
        state.current_epoch(slots_per_epoch),
        epoch,
        activation_exit_delay,
        epochs_per_historical_vector,
    )

    return state.active_index_roots[epoch % epochs_per_historical_vector]


def generate_seed(state: 'BeaconState',
                  epoch: Epoch,
                  committee_config: CommitteeConfig) -> Hash32:
    """
    Generate a seed for the given ``epoch``.
    """
    randao_mix = get_randao_mix(
        state=state,
        epoch=Epoch(
            epoch +
            committee_config.EPOCHS_PER_HISTORICAL_VECTOR -
            committee_config.MIN_SEED_LOOKAHEAD
        ),
        slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
        epochs_per_historical_vector=committee_config.EPOCHS_PER_HISTORICAL_VECTOR,
        perform_validation=False,
    )
    active_index_root = get_active_index_root(
        state=state,
        epoch=epoch,
        slots_per_epoch=committee_config.SLOTS_PER_EPOCH,
        activation_exit_delay=committee_config.ACTIVATION_EXIT_DELAY,
        epochs_per_historical_vector=committee_config.EPOCHS_PER_HISTORICAL_VECTOR,
    )
    epoch_as_bytes = epoch.to_bytes(32, byteorder="little")

    return hash_eth2(randao_mix + active_index_root + epoch_as_bytes)


def get_total_balance(state: 'BeaconState',
                      validator_indices: Sequence[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of an array of validators.
    """
    return Gwei(
        max(
            sum(
                state.validators[index].effective_balance
                for index in validator_indices
            ),
            1
        )
    )


def _get_fork_version(fork: Fork, epoch: Epoch) -> bytes:
    """
    Return the current ``fork_version`` from the given ``fork`` and ``epoch``.
    """
    if epoch < fork.epoch:
        return fork.previous_version
    else:
        return fork.current_version


def bls_domain(domain_type: SignatureDomain, fork_version: bytes=b'\x00' * 4) -> int:
    return int.from_bytes(domain_type.to_bytes(4, 'little') + fork_version, 'little')


def get_domain(state: 'BeaconState',
               domain_type: SignatureDomain,
               slots_per_epoch: int,
               message_epoch: Epoch=None) -> int:
    """
    Return the domain number of the current fork and ``domain_type``.
    """
    epoch = state.current_epoch(slots_per_epoch) if message_epoch is None else message_epoch
    fork_version = _get_fork_version(state.fork, epoch)
    return bls_domain(domain_type, fork_version)
