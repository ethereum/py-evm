import random

import pytest

from eth_utils import (
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
    FAR_FUTURE_EPOCH,
)

from eth2.beacon.types.attestation_data import (
    AttestationData,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.validator_records import ValidatorRecord

from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
    get_block_root,
    get_state_root,
    get_domain,
    get_effective_balance,
    get_delayed_activation_exit_epoch,
    get_fork_version,
    get_total_balance,
    is_double_vote,
    is_surround_vote,
)

from tests.eth2.beacon.helpers import (
    get_pseudo_chain,
)


def generate_mock_latest_historical_roots(
        genesis_block,
        current_slot,
        slots_per_epoch,
        slots_per_historical_root):
    assert current_slot < slots_per_historical_root

    chain_length = (current_slot // slots_per_epoch + 1) * slots_per_epoch
    blocks = get_pseudo_chain(chain_length, genesis_block)
    latest_block_roots = [
        block.hash
        for block in blocks[:current_slot]
    ] + [
        ZERO_HASH32
        for _ in range(slots_per_historical_root - current_slot)
    ]
    return blocks, latest_block_roots


#
# Get historical roots
#
@pytest.mark.parametrize(
    (
        'genesis_slot,'
    ),
    [
        (0),
    ],
)
@pytest.mark.parametrize(
    (
        'current_slot,target_slot,success'
    ),
    [
        (10, 0, True),
        (10, 9, True),
        (10, 10, False),
        (128, 0, True),
        (128, 127, True),
        (128, 128, False),
    ],
)
def test_get_block_root(sample_beacon_state_params,
                        current_slot,
                        target_slot,
                        success,
                        slots_per_epoch,
                        slots_per_historical_root,
                        sample_block):
    blocks, latest_block_roots = generate_mock_latest_historical_roots(
        sample_block,
        current_slot,
        slots_per_epoch,
        slots_per_historical_root,
    )
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=current_slot,
        latest_block_roots=latest_block_roots,
    )

    if success:
        block_root = get_block_root(
            state,
            target_slot,
            slots_per_historical_root,
        )
        assert block_root == blocks[target_slot].root
    else:
        with pytest.raises(ValidationError):
            get_block_root(
                state,
                target_slot,
                slots_per_historical_root,
            )


@pytest.mark.parametrize(
    (
        'genesis_slot,'
    ),
    [
        (0),
    ],
)
@pytest.mark.parametrize(
    (
        'current_slot,target_slot,success'
    ),
    [
        (10, 0, True),
        (10, 9, True),
        (10, 10, False),
        (128, 0, True),
        (128, 127, True),
        (128, 128, False),
    ],
)
def test_get_state_root(sample_beacon_state_params,
                        current_slot,
                        target_slot,
                        success,
                        slots_per_epoch,
                        slots_per_historical_root,
                        sample_block):
    blocks, latest_state_roots = generate_mock_latest_historical_roots(
        sample_block,
        current_slot,
        slots_per_epoch,
        slots_per_historical_root,
    )
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=current_slot,
        latest_state_roots=latest_state_roots,
    )

    if success:
        state_root = get_state_root(
            state,
            target_slot,
            slots_per_historical_root,
        )
        assert state_root == blocks[target_slot].root
    else:
        with pytest.raises(ValidationError):
            get_state_root(
                state,
                target_slot,
                slots_per_historical_root,
            )


def test_get_active_validator_indices(sample_validator_record_params):
    current_epoch = 1
    # 3 validators are ACTIVE
    validators = [
        ValidatorRecord(
            **sample_validator_record_params,
        ).copy(
            activation_epoch=0,
            exit_epoch=FAR_FUTURE_EPOCH,
        )
        for i in range(3)
    ]
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 3

    validators[0] = validators[0].copy(
        activation_epoch=current_epoch + 1,  # activation_epoch > current_epoch
    )
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 2

    validators[1] = validators[1].copy(
        exit_epoch=current_epoch,  # current_epoch == exit_epoch
    )
    active_validator_indices = get_active_validator_indices(validators, current_epoch)
    assert len(active_validator_indices) == 1


@pytest.mark.parametrize(
    (
        'balance,'
        'max_deposit_amount,'
        'expected'
    ),
    [
        (
            1 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            1 * GWEI_PER_ETH,
        ),
        (
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
        (
            33 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        )
    ]
)
def test_get_effective_balance(balance,
                               max_deposit_amount,
                               expected,
                               sample_validator_record_params):
    balances = (balance,)
    result = get_effective_balance(balances, 0, max_deposit_amount)
    assert result == expected


@pytest.mark.parametrize(
    (
        'validator_balances,'
        'validator_indices,'
        'max_deposit_amount,'
        'expected'
    ),
    [
        (
            tuple(),
            tuple(),
            1 * GWEI_PER_ETH,
            0,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (0, 1),
            32 * GWEI_PER_ETH,
            64 * GWEI_PER_ETH,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (1,),
            32 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
        (
            (32 * GWEI_PER_ETH, 32 * GWEI_PER_ETH),
            (0, 1),
            16 * GWEI_PER_ETH,
            32 * GWEI_PER_ETH,
        ),
    ]
)
def test_get_total_balance(validator_balances,
                           validator_indices,
                           max_deposit_amount,
                           expected):
    total_balance = get_total_balance(validator_balances, validator_indices, max_deposit_amount)
    assert total_balance == expected


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'epoch,'
        'current_epoch,'
        'expected'
    ),
    [
        (b'\x00' * 4, b'\x00' * 4, 0, 0, b'\x00' * 4),
        (b'\x00' * 4, b'\x00' * 4, 0, 1, b'\x00' * 4),
        (b'\x00' * 4, b'\x11' * 4, 20, 10, b'\x00' * 4),
        (b'\x00' * 4, b'\x11' * 4, 20, 20, b'\x11' * 4),
        (b'\x00' * 4, b'\x11' * 4, 10, 20, b'\x11' * 4),
    ]
)
def test_get_fork_version(previous_version,
                          current_version,
                          epoch,
                          current_epoch,
                          expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        epoch=epoch,
    )
    assert expected == get_fork_version(
        fork,
        current_epoch,
    )


@pytest.mark.parametrize(
    (
        'previous_version,'
        'current_version,'
        'epoch,'
        'current_epoch,'
        'domain_type,'
        'expected'
    ),
    [
        (
            b'\x11' * 4,
            b'\x22' * 4,
            4,
            4,
            1,
            int.from_bytes(b'\x22' * 4 + b'\x01\x00\x00\x00', 'little'),
        ),
        (
            b'\x11' * 4,
            b'\x22' * 4,
            4,
            4 - 1,
            1,
            int.from_bytes(b'\x11' * 4 + b'\x01\x00\x00\x00', 'little'),
        ),
    ]
)
def test_get_domain(previous_version,
                    current_version,
                    epoch,
                    current_epoch,
                    domain_type,
                    expected):
    fork = Fork(
        previous_version=previous_version,
        current_version=current_version,
        epoch=epoch,
    )
    assert expected == get_domain(
        fork=fork,
        epoch=current_epoch,
        domain_type=domain_type,
    )


def test_is_double_vote(sample_attestation_data_params, slots_per_epoch):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': 12345,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': 12345,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_double_vote(attestation_data_1, attestation_data_2, slots_per_epoch)

    attestation_data_3_params = {
        **sample_attestation_data_params,
        'slot': 54321,
    }
    attestation_data_3 = AttestationData(**attestation_data_3_params)

    assert not is_double_vote(attestation_data_1, attestation_data_3, slots_per_epoch)


@pytest.mark.parametrize(
    (
        'slots_per_epoch,'
        'attestation_1_slot,'
        'attestation_1_justified_epoch,'
        'attestation_2_slot,'
        'attestation_2_justified_epoch,'
        'expected'
    ),
    [
        (1, 0, 0, 0, 0, False),
        # not (attestation_1_justified_epoch < attestation_2_justified_epoch
        (1, 4, 3, 3, 2, False),
        # not (slot_to_epoch(attestation_2_slot) < slot_to_epoch(attestation_1_slot))
        (1, 4, 0, 4, 3, False),
        (1, 4, 0, 3, 2, True),
    ],
)
def test_is_surround_vote(sample_attestation_data_params,
                          slots_per_epoch,
                          attestation_1_slot,
                          attestation_1_justified_epoch,
                          attestation_2_slot,
                          attestation_2_justified_epoch,
                          expected):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': attestation_1_slot,
        'justified_epoch': attestation_1_justified_epoch,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': attestation_2_slot,
        'justified_epoch': attestation_2_justified_epoch,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_surround_vote(attestation_data_1, attestation_data_2, slots_per_epoch) == expected


def test_get_delayed_activation_exit_epoch(activation_exit_delay):
    epoch = random.randint(0, FAR_FUTURE_EPOCH)
    entry_exit_effect_epoch = get_delayed_activation_exit_epoch(
        epoch,
        activation_exit_delay,
    )
    assert entry_exit_effect_epoch == (epoch + 1 + activation_exit_delay)


def test_generate_seed(monkeypatch,
                       genesis_state,
                       slots_per_epoch,
                       min_seed_lookahead,
                       activation_exit_delay,
                       latest_active_index_roots_length,
                       latest_randao_mixes_length):
    from eth2.beacon import helpers

    def mock_get_randao_mix(state,
                            epoch,
                            slots_per_epoch,
                            latest_randao_mixes_length):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            latest_randao_mixes_length.to_bytes(32, byteorder='little')
        )

    def mock_get_active_index_root(state,
                                   epoch,
                                   slots_per_epoch,
                                   activation_exit_delay,
                                   latest_active_index_roots_length):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            slots_per_epoch.to_bytes(32, byteorder='little') +
            latest_active_index_roots_length.to_bytes(32, byteorder='little')
        )

    monkeypatch.setattr(
        helpers,
        'get_randao_mix',
        mock_get_randao_mix
    )
    monkeypatch.setattr(
        helpers,
        'get_active_index_root',
        mock_get_active_index_root
    )

    state = genesis_state
    epoch = 1

    epoch_as_bytes = epoch.to_bytes(32, 'little')

    seed = generate_seed(
        state=state,
        epoch=epoch,
        slots_per_epoch=slots_per_epoch,
        min_seed_lookahead=min_seed_lookahead,
        activation_exit_delay=activation_exit_delay,
        latest_active_index_roots_length=latest_active_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    assert seed == hash_eth2(
        mock_get_randao_mix(
            state=state,
            epoch=(epoch - min_seed_lookahead),
            slots_per_epoch=slots_per_epoch,
            latest_randao_mixes_length=latest_randao_mixes_length,
        ) + mock_get_active_index_root(
            state=state,
            epoch=epoch,
            slots_per_epoch=slots_per_epoch,
            activation_exit_delay=activation_exit_delay,
            latest_active_index_roots_length=latest_active_index_roots_length,
        ) + epoch_as_bytes
    )
