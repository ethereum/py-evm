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

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.enums import (
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
    validate_epoch_for_active_randao_mix,
)

if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.forks import Fork  # noqa: F401
    from eth2.beacon.types.slashable_attestations import SlashableAttestation  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


#
# Time unit convertion
#
def slot_to_epoch(slot: Slot, slots_per_epoch: int) -> Epoch:
    return Epoch(slot // slots_per_epoch)


def get_epoch_start_slot(epoch: Epoch, slots_per_epoch: int) -> Slot:
    return Slot(epoch * slots_per_epoch)


def _get_historical_root(
        historical_roots: Sequence[Hash32],
        state_slot: Slot,
        slot: Slot,
        slots_per_historical_root: int) -> Hash32:
    """
    Return the historical root at a recent ``slot``.

    An internal helper function used to grab a recent
    block root or state root.
    """
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
    if slot >= state_slot:
        raise ValidationError(
            "slot ({}) should be less than state.slot ({})".format(
                slot,
                state_slot,
            )
        )
    return historical_roots[slot % slots_per_historical_root]


def get_block_root(state: 'BeaconState',
                   slot: Slot,
                   slots_per_historical_root: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    return _get_historical_root(
        state.latest_block_roots,
        state.slot,
        slot,
        slots_per_historical_root,
    )


def get_state_root(state: 'BeaconState',
                   slot: Slot,
                   slots_per_historical_root: int) -> Hash32:
    """
    Return the state root at a recent ``slot``.
    """
    return _get_historical_root(
        state.latest_state_roots,
        state.slot,
        slot,
        slots_per_historical_root,
    )


def get_randao_mix(state: 'BeaconState',
                   epoch: Epoch,
                   slots_per_epoch: int,
                   latest_randao_mixes_length: int) -> Hash32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    validate_epoch_for_active_randao_mix(
        state.current_epoch(slots_per_epoch),
        epoch,
        latest_randao_mixes_length,
    )

    return state.latest_randao_mixes[epoch % latest_randao_mixes_length]


def get_active_validator_indices(validators: Sequence['ValidatorRecord'],
                                 epoch: Epoch) -> Tuple[ValidatorIndex, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        ValidatorIndex(index)
        for index, validator in enumerate(validators)
        if validator.is_active(epoch)
    )


def generate_seed(state: 'BeaconState',
                  epoch: Epoch,
                  slots_per_epoch: int,
                  min_seed_lookahead: int,
                  activation_exit_delay: int,
                  latest_active_index_roots_length: int,
                  latest_randao_mixes_length: int) -> Hash32:
    """
    Generate a seed for the given ``epoch``.
    """
    randao_mix = get_randao_mix(
        state=state,
        epoch=Epoch(epoch - min_seed_lookahead),
        slots_per_epoch=slots_per_epoch,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    active_index_root = get_active_index_root(
        state=state,
        epoch=epoch,
        slots_per_epoch=slots_per_epoch,
        activation_exit_delay=activation_exit_delay,
        latest_active_index_roots_length=latest_active_index_roots_length,
    )
    epoch_as_bytes = epoch.to_bytes(32, byteorder="little")

    return hash_eth2(randao_mix + active_index_root + epoch_as_bytes)


def get_active_index_root(state: 'BeaconState',
                          epoch: Epoch,
                          slots_per_epoch: int,
                          activation_exit_delay: int,
                          latest_active_index_roots_length: int) -> Hash32:
    """
    Return the index root at a recent ``epoch``.
    """
    validate_epoch_for_active_index_root(
        state.current_epoch(slots_per_epoch),
        epoch,
        activation_exit_delay,
        latest_active_index_roots_length,
    )

    return state.latest_active_index_roots[epoch % latest_active_index_roots_length]


def get_effective_balance(
        validator_balances: Sequence[Gwei],
        index: ValidatorIndex,
        max_deposit_amount: Gwei) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a
    ``validator`` with the given ``index``.
    """
    return min(validator_balances[index], max_deposit_amount)


def get_total_balance(validator_balances: Sequence[Gwei],
                      validator_indices: Sequence[ValidatorIndex],
                      max_deposit_amount: Gwei) -> Gwei:
    """
    Return the combined effective balance of an array of validators.
    """
    return Gwei(sum(
        get_effective_balance(validator_balances, index, max_deposit_amount)
        for index in validator_indices
    ))


def get_fork_version(fork: 'Fork',
                     epoch: Epoch) -> bytes:
    """
    Return the current ``fork_version`` from the given ``fork`` and ``epoch``.
    """
    if epoch < fork.epoch:
        return fork.previous_version
    else:
        return fork.current_version


def get_domain(fork: 'Fork',
               epoch: Epoch,
               domain_type: SignatureDomain) -> int:
    """
    Return the domain number of the current fork and ``domain_type``.
    """
    return int.from_bytes(
        get_fork_version(
            fork,
            epoch,
        ) + domain_type.to_bytes(4, 'little'),
        'little'
    )


def is_double_vote(attestation_data_1: 'AttestationData',
                   attestation_data_2: 'AttestationData',
                   slots_per_epoch: int) -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'double vote'.
    """
    return (
        slot_to_epoch(attestation_data_1.slot, slots_per_epoch) ==
        slot_to_epoch(attestation_data_2.slot, slots_per_epoch)
    )


def is_surround_vote(attestation_data_1: 'AttestationData',
                     attestation_data_2: 'AttestationData',
                     slots_per_epoch: int) -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'surround vote'.

    Note: parameter order matters as this function only checks
    that ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    source_epoch_1 = attestation_data_1.justified_epoch
    source_epoch_2 = attestation_data_2.justified_epoch
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot, slots_per_epoch)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot, slots_per_epoch)
    return source_epoch_1 < source_epoch_2 and target_epoch_2 < target_epoch_1


def get_delayed_activation_exit_epoch(
        epoch: Epoch,
        activation_exit_delay: int) -> Epoch:
    """
    An entry or exit triggered in the ``epoch`` given by the input takes effect at
    the epoch given by the output.
    """
    return Epoch(epoch + 1 + activation_exit_delay)
