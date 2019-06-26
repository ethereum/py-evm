import random

import pytest

from eth_utils import (
    ValidationError,
    to_tuple,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
    GWEI_PER_ETH,
    FAR_FUTURE_EPOCH,
)

from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.validators import Validator

from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
    get_block_root,
    get_domain,
    _get_fork_version,
    get_total_balance,
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


def generate_mock_latest_historical_roots(
        genesis_block,
        current_slot,
        slots_per_epoch,
        slots_per_historical_root):
    assert current_slot < slots_per_historical_root

    chain_length = (current_slot // slots_per_epoch + 1) * slots_per_epoch
    blocks = get_pseudo_chain(chain_length, genesis_block)
    block_roots = [
        block.signing_root
        for block in blocks[:current_slot]
    ] + [
        ZERO_HASH32
        for _ in range(slots_per_historical_root - current_slot)
    ]
    return blocks, block_roots


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
    blocks, block_roots = generate_mock_latest_historical_roots(
        sample_block,
        current_slot,
        slots_per_epoch,
        slots_per_historical_root,
    )
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=current_slot,
        block_roots=block_roots,
    )

    if success:
        block_root = get_block_root(
            state,
            target_slot,
            slots_per_historical_root,
        )
        assert block_root == blocks[target_slot].signing_root
    else:
        with pytest.raises(ValidationError):
            get_block_root(
                state,
                target_slot,
                slots_per_historical_root,
            )


def test_get_active_validator_indices(sample_validator_record_params):
    current_epoch = 1
    # 3 validators are ACTIVE
    validators = [
        Validator(
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
        'balances,'
        'validator_indices,'
        'max_effective_balance,'
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
def test_get_total_balance(balances,
                           validator_indices,
                           max_effective_balance,
                           expected):
    total_balance = get_total_balance(balances, validator_indices, max_effective_balance)
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


def test_generate_seed(monkeypatch,
                       genesis_state,
                       committee_config,
                       slots_per_epoch,
                       min_seed_lookahead,
                       activation_exit_delay,
                       epochs_per_historical_vector):
    from eth2.beacon import helpers

    def mock_get_randao_mix(state,
                            epoch,
                            slots_per_epoch,
                            epochs_per_historical_vector):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            epochs_per_historical_vector.to_bytes(32, byteorder='little')
        )

    def mock_get_active_index_root(state,
                                   epoch,
                                   slots_per_epoch,
                                   activation_exit_delay,
                                   epochs_per_historical_vector):
        return hash_eth2(
            state.root +
            epoch.to_bytes(32, byteorder='little') +
            slots_per_epoch.to_bytes(32, byteorder='little') +
            epochs_per_historical_vector.to_bytes(32, byteorder='little')
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
        committee_config=committee_config,
    )
    assert seed == hash_eth2(
        mock_get_randao_mix(
            state=state,
            epoch=(epoch - min_seed_lookahead),
            slots_per_epoch=slots_per_epoch,
            epochs_per_historical_vector=epochs_per_historical_vector,
        ) + mock_get_active_index_root(
            state=state,
            epoch=epoch,
            slots_per_epoch=slots_per_epoch,
            activation_exit_delay=activation_exit_delay,
            epochs_per_historical_vector=epochs_per_historical_vector,
        ) + epoch_as_bytes
    )
