import copy
import random

import itertools
import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth_utils import (
    big_endian_to_int,
    ValidationError,
)

from eth_utils.toolz import (
    assoc,
    isdistinct,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2._utils.bitfield import (
    get_empty_bitfield,
    set_voted,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.exceptions import NoWinningRootError
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.types.attestations import (
    Attestation,
)
from eth2.beacon.types.attestation_data import (
    AttestationData,
)
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.slashable_attestations import SlashableAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_records import ValidatorRecord
from eth2.beacon.helpers import (
    _get_block_root,
    generate_aggregate_pubkeys,
    generate_seed,
    get_active_validator_indices,
    get_attesting_validator_indices,
    get_attestation_participants,
    get_beacon_proposer_index,
    get_epoch_committee_count,
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
    get_current_epoch_attestations,
    get_domain,
    get_effective_balance,
    get_entry_exit_effect_epoch,
    get_fork_version,
    get_previous_epoch_attestations,
    get_previous_epoch_committee_count,
    get_pubkey_for_indices,
    get_winning_root,
    get_shuffling,
    is_double_vote,
    is_surround_vote,
    slot_to_epoch,
    validate_slashable_attestation,
    verify_slashable_attestation_signature,
)
import eth2._utils.bls as bls

from tests.eth2.beacon.helpers import (
    get_pseudo_chain,
)


@pytest.fixture()
def sample_block(sample_beacon_block_params):
    return SerenityBeaconBlock(**sample_beacon_block_params)


@pytest.fixture()
def sample_state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


def generate_mock_latest_block_roots(
        genesis_block,
        current_slot,
        epoch_length,
        latest_block_roots_length):
    assert current_slot < latest_block_roots_length

    chain_length = (current_slot // epoch_length + 1) * epoch_length
    blocks = get_pseudo_chain(chain_length, genesis_block)
    latest_block_roots = [
        block.hash
        for block in blocks[:current_slot]
    ] + [
        ZERO_HASH32
        for _ in range(latest_block_roots_length - current_slot)
    ]
    return blocks, latest_block_roots


#
# Get block rootes
#
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
def test_get_block_root(current_slot,
                        target_slot,
                        success,
                        epoch_length,
                        latest_block_roots_length,
                        sample_block):
    blocks, latest_block_roots = generate_mock_latest_block_roots(
        sample_block,
        current_slot,
        epoch_length,
        latest_block_roots_length,
    )

    if success:
        block_root = _get_block_root(
            latest_block_roots,
            current_slot,
            target_slot,
            latest_block_roots_length,
        )
        assert block_root == blocks[target_slot].root
    else:
        with pytest.raises(ValidationError):
            _get_block_root(
                latest_block_roots,
                current_slot,
                target_slot,
                latest_block_roots_length,
            )


#
# Shuffling
#
@pytest.mark.parametrize(
    (
        'active_validator_count,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'expected_committee_count'
    ),
    [
        (1000, 20, 10, 50, 40),  # SHARD_COUNT // EPOCH_LENGTH
        (500, 20, 10, 100, 40),  # active_validator_count // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE
        (20, 10, 3, 10, 10),  # 1
        (20, 10, 3, 5, 10),  # 1
        (40, 5, 10, 2, 5),  # 1
    ],
)
def test_get_epoch_committee_count(
        active_validator_count,
        epoch_length,
        target_committee_size,
        shard_count,
        expected_committee_count):
    assert expected_committee_count == get_epoch_committee_count(
        active_validator_count=active_validator_count,
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'epoch'
    ),
    [
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 0),
        (1000, 20, 10, 100, 1),
        (20, 10, 3, 10, 0),  # active_validators_size < epoch_length * target_committee_size
        (20, 10, 3, 10, 0),
        (20, 10, 3, 10, 1),
    ],
)
def test_get_shuffling_is_complete(activated_genesis_validators,
                                   epoch_length,
                                   target_committee_size,
                                   shard_count,
                                   epoch):
    shuffling = get_shuffling(
        seed=b'\x35' * 32,
        validators=activated_genesis_validators,
        epoch=epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == epoch_length
    assert len(shuffling) > 0
    for committee in shuffling:
        assert len(committee) <= target_committee_size
        assert len(committee) > 0
    validator_indices = tuple(
        itertools.chain(
            [
                validator_index
                for committee in shuffling
                for validator_index in committee
            ]
        )
    )
    assert isdistinct(validator_indices)
    activated_genesis_validator_indices = tuple(
        index
        for index in range(len(activated_genesis_validators))
    )
    assert sorted(validator_indices) == sorted(activated_genesis_validator_indices)


@pytest.mark.parametrize(
    (
        'n, target_committee_size, shard_count, len_active_validators,'
        'previous_calculation_epoch, current_calculation_epoch,'
        'get_prev_or_cur_epoch_committee_count,'
        'delayed_activation_epoch'
    ),
    [
        (
            100, 10, 20, 20,
            5, 10,
            get_previous_epoch_committee_count,
            5 + 1,
        ),
        (
            100, 10, 20, 100,
            5, 10,
            get_previous_epoch_committee_count,
            5 + 1,
        ),
        (
            100, 10, 20, 20,
            5, 10,
            get_current_epoch_committee_count,
            10 + 1,
        ),
        (
            100, 10, 20, 100,
            5, 10,
            get_current_epoch_committee_count,
            10 + 1,
        ),
    ],
)
def test_get_prev_or_cur_epoch_committee_count(
        monkeypatch,
        n_validators_state,
        epoch_length,
        n,
        target_committee_size,
        shard_count,
        len_active_validators,
        previous_calculation_epoch,
        current_calculation_epoch,
        get_prev_or_cur_epoch_committee_count,
        delayed_activation_epoch):
    from eth2.beacon import helpers

    def mock_get_epoch_committee_count(
            active_validator_count,
            shard_count,
            epoch_length,
            target_committee_size):
        return active_validator_count // shard_count

    monkeypatch.setattr(
        helpers,
        'get_epoch_committee_count',
        mock_get_epoch_committee_count
    )

    state = n_validators_state.copy(
        slot=0,
        previous_calculation_epoch=previous_calculation_epoch,
        current_calculation_epoch=current_calculation_epoch,
    )
    for index in range(len(state.validator_registry)):
        if index < len_active_validators:
            validator = state.validator_registry[index].copy(
                activation_epoch=0,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )
        else:
            validator = state.validator_registry[index].copy(
                activation_epoch=delayed_activation_epoch,
            )
            state = state.update_validator_registry(
                index,
                validator,
            )

    result_committee_count = get_prev_or_cur_epoch_committee_count(
        state=state,
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )
    expected_committee_count = len_active_validators // shard_count

    assert result_committee_count == expected_committee_count


@pytest.mark.parametrize(
    (
        'current_slot,'
        'slot,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
    ),
    [
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) == current_epoch
        (0, 5, 10, 10, 10),
        # genesis_epoch == previous_epoch == slot_to_epoch(slot) < current_epoch
        (10, 5, 10, 10, 10),
        # genesis_epoch < previous_epoch == slot_to_epoch(slot) < current_epoch
        (20, 11, 10, 10, 10),
        # genesis_epoch == previous_epoch < slot_to_epoch(slot) == current_epoch
        (10, 11, 10, 10, 10),
    ],
)
def test_get_crosslink_committees_at_slot(
        n_validators_state,
        current_slot,
        slot,
        epoch_length,
        target_committee_size,
        shard_count,
        genesis_epoch):

    state = n_validators_state.copy(
        slot=current_slot,
    )

    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    assert len(crosslink_committees_at_slot) > 0
    for crosslink_committee in crosslink_committees_at_slot:
        committee, shard = crosslink_committee
        assert len(committee) > 0
        assert shard < shard_count


#
# Get proposer postition
#
@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'committee,'
        'slot,'
        'success,'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            0,
            True,
        ),
        (
            100,
            64,
            (),
            0,
            False,
        ),
    ]
)
def test_get_beacon_proposer_index(
        monkeypatch,
        num_validators,
        epoch_length,
        committee,
        slot,
        success,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count):

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )
    if success:
        proposer_index = get_beacon_proposer_index(
            sample_state,
            slot,
            genesis_epoch,
            epoch_length,
            target_committee_size,
            shard_count,
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                genesis_epoch,
                epoch_length,
                target_committee_size,
                shard_count,
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
        'num_validators,'
        'epoch_length,'
        'committee,'
        'aggregation_bitfield,'
        'expected'
    ),
    [
        (
            100,
            64,
            (10, 11, 12),
            b'\00',
            (),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x80',
            (10,),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\xc0',
            (10, 11),
        ),
        (
            100,
            64,
            (10, 11, 12),
            b'\x00\x00',
            ValueError(),
        ),
    ]
)
def test_get_attestation_participants(
        monkeypatch,
        num_validators,
        epoch_length,
        committee,
        aggregation_bitfield,
        expected,
        sample_state,
        genesis_epoch,
        target_committee_size,
        shard_count,
        sample_attestation_data_params):
    shard = 1

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    attestation_data = AttestationData(**sample_attestation_data_params).copy(
        slot=0,
        shard=shard,
    )
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            get_attestation_participants(
                state=sample_state,
                attestation_data=attestation_data,
                bitfield=aggregation_bitfield,
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length,
                target_committee_size=target_committee_size,
                shard_count=shard_count,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            attestation_data=attestation_data,
            bitfield=aggregation_bitfield,
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
            shard_count=shard_count,
        )

        assert result == expected


@settings(max_examples=1)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'target_committee_size,'
        'shard_count'
    ),
    [
        (
            16,
            32,
        ),
    ]
)
def test_get_attesting_validator_indices(
        random,
        monkeypatch,
        target_committee_size,
        shard_count,
        genesis_epoch,
        epoch_length,
        sample_state,
        sample_attestation_data_params,
        sample_attestation_params):
    shard = 1
    committee = tuple([i for i in range(target_committee_size)])

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    # Validators attesting to two shard block roots
    shard_block_root_1 = hash_eth2(b'shard_block_root_1')
    shard_block_root_2 = hash_eth2(b'shard_block_root_2')

    # Random sampling half the committee.
    # `attestation_participants_1` and `attestation_participants_2` are expected to have
    # overlapping participants.
    attestation_participants_1 = random.sample(committee, target_committee_size // 2)
    attestation_participants_2 = random.sample(committee, target_committee_size // 2)
    not_attestation_participants_1 = [i for i in committee if i not in attestation_participants_1]

    # Generate bitfield of each participants set
    aggregation_bitfield_1 = get_empty_bitfield(target_committee_size)
    aggregation_bitfield_2 = get_empty_bitfield(target_committee_size)
    not_aggregation_bitfield_1 = get_empty_bitfield(target_committee_size)
    for committee_index_1, committee_index_2, committee_index_3 in zip(
            attestation_participants_1, attestation_participants_2, not_attestation_participants_1):
        aggregation_bitfield_1 = set_voted(aggregation_bitfield_1, committee_index_1)
        aggregation_bitfield_2 = set_voted(aggregation_bitfield_2, committee_index_2)
        not_aggregation_bitfield_1 = set_voted(not_aggregation_bitfield_1, committee_index_3)

    # `attestions` contains attestation to different block root by different set of participants
    attestations = [
        # Attestation to `shard_block_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_1,
            ),
            aggregation_bitfield=aggregation_bitfield_1
        ),
        # Attestation to `shard_block_root_1` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_1,
            ),
            aggregation_bitfield=aggregation_bitfield_2
        ),
        # Attestation to `shard_block_root_2` by `not_attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=shard_block_root_2,
            ),
            aggregation_bitfield=not_aggregation_bitfield_1
        ),
    ]

    shard_block_root_1_attesting_validator = get_attesting_validator_indices(
        state=sample_state,
        attestations=attestations,
        shard=shard,
        shard_block_root=shard_block_root_1,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    # Check that result is the union of two participants set
    # `attestation_participants_1` and `attestation_participants_2`
    assert set(shard_block_root_1_attesting_validator) == set(
        attestation_participants_1 + attestation_participants_2)
    assert len(shard_block_root_1_attesting_validator) == len(
        set(attestation_participants_1 + attestation_participants_2))

    shard_block_root_2_attesting_validator = get_attesting_validator_indices(
        state=sample_state,
        attestations=attestations,
        shard=shard,
        shard_block_root=shard_block_root_2,
        genesis_epoch=genesis_epoch,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    # Check that result is the `not_attestation_participants_1` set
    assert set(shard_block_root_2_attesting_validator) == set(not_attestation_participants_1)
    assert len(shard_block_root_2_attesting_validator) == len(not_attestation_participants_1)


@settings(max_examples=1)
@given(random=st.randoms())
def test_get_current_and_previous_epoch_attestations(random,
                                                     sample_state,
                                                     genesis_epoch,
                                                     epoch_length,
                                                     sample_attestation_data_params,
                                                     sample_attestation_params):
    num_previous_epoch_attestation, num_current_epoch_attestation = random.sample(
        range(epoch_length),
        2,
    )
    previous_epoch_attestion_slots = random.sample(
        range(epoch_length),
        num_previous_epoch_attestation,
    )
    current_epoch_attestion_slots = random.sample(
        range(epoch_length, epoch_length * 2),
        num_current_epoch_attestation,
    )

    previous_epoch_attestations = []
    for slot in previous_epoch_attestion_slots:
        previous_epoch_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                ),
            )
        )
    current_epoch_attestations = []
    for slot in current_epoch_attestion_slots:
        current_epoch_attestations.append(
            Attestation(**sample_attestation_params).copy(
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=slot,
                ),
            )
        )

    state = sample_state.copy(
        slot=(epoch_length * 2 - 1),
        latest_attestations=(previous_epoch_attestations + current_epoch_attestations),
    )
    assert set(previous_epoch_attestations) == set(
        get_previous_epoch_attestations(state, epoch_length, genesis_epoch))
    assert set(current_epoch_attestations) == set(
        get_current_epoch_attestations(state, epoch_length))


@settings(max_examples=10)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'target_committee_size,'
        'block_root_1_participants,'
        'block_root_2_participants,'
    ),
    [
        (
            16,
            (1, 3),
            (2, 4, 6, 8)
        ),
        (
            16,
            # vote tie; lower root value is favored
            (1, 3, 5, 7),
            (2, 4, 6, 8)
        ),
        (
            16,
            # no votes; no winning root
            (),
            ()
        ),
    ]
)
def test_get_winning_root(
        random,
        monkeypatch,
        target_committee_size,
        block_root_1_participants,
        block_root_2_participants,
        config,
        n_validators_state,
        sample_attestation_data_params,
        sample_attestation_params):
    shard = 1
    committee = tuple([i for i in range(target_committee_size)])

    from eth2.beacon import helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              genesis_epoch,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
        return (
            (committee, shard,),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    competing_block_roots = [
        hash_eth2(bytearray(random.getrandbits(8) for _ in range(10))),
        hash_eth2(bytearray(random.getrandbits(8) for _ in range(10)))
    ]

    # Generate bitfield of each participants set
    root_1_participants_bitfield = get_empty_bitfield(target_committee_size)
    root_2_participants_bitfield = get_empty_bitfield(target_committee_size)
    for i in block_root_1_participants:
        root_1_participants_bitfield = set_voted(root_1_participants_bitfield, i)
    for i in block_root_2_participants:
        root_2_participants_bitfield = set_voted(root_2_participants_bitfield, i)

    # `attestions` contains attestation to different block root by different set of participants
    attestations = [
        # Attestation to `shard_block_root_1` by `attestation_participants_1`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=competing_block_roots[0],
            ),
            aggregation_bitfield=root_1_participants_bitfield
        ),
        # Attestation to `shard_block_root_2` by `attestation_participants_2`
        Attestation(**sample_attestation_params).copy(
            data=AttestationData(**sample_attestation_data_params).copy(
                shard=shard,
                shard_block_root=competing_block_roots[1],
            ),
            aggregation_bitfield=root_2_participants_bitfield
        ),
    ]

    try:
        winning_root, attesting_balance = get_winning_root(
            state=n_validators_state,
            shard=shard,
            attestations=attestations,
            genesis_epoch=config.GENESIS_EPOCH,
            epoch_length=config.EPOCH_LENGTH,
            max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
            target_committee_size=config.TARGET_COMMITTEE_SIZE,
            shard_count=config.SHARD_COUNT,
        )
        attesting_validators_indices = get_attesting_validator_indices(
            state=n_validators_state,
            attestations=attestations,
            shard=shard,
            shard_block_root=winning_root,
            genesis_epoch=config.GENESIS_EPOCH,
            epoch_length=config.EPOCH_LENGTH,
            target_committee_size=config.TARGET_COMMITTEE_SIZE,
            shard_count=config.SHARD_COUNT,
        )
        total_attesting_balance = sum(
            get_effective_balance(
                n_validators_state.validator_balances,
                i,
                config.MAX_DEPOSIT_AMOUNT
            )
            for i in attesting_validators_indices
        )
        assert attesting_balance == total_attesting_balance
    except NoWinningRootError:
        assert len(block_root_1_participants) == 0 and len(block_root_2_participants) == 0
    else:
        if len(block_root_1_participants) == len(block_root_2_participants):
            root_1_as_int = big_endian_to_int(competing_block_roots[0])
            root_2_as_int = big_endian_to_int(competing_block_roots[1])
            if root_1_as_int < root_2_as_int:
                assert winning_root == competing_block_roots[0]
            else:
                assert winning_root == competing_block_roots[1]
        elif len(block_root_1_participants) < len(block_root_2_participants):
            assert winning_root == competing_block_roots[1]
        else:
            assert winning_root == competing_block_roots[0]


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
        'previous_version,'
        'current_version,'
        'epoch,'
        'current_epoch,'
        'expected'
    ),
    [
        (0, 0, 0, 0, 0),
        (0, 0, 0, 1, 0),
        (0, 1, 20, 10, 0),
        (0, 1, 20, 20, 1),
        (0, 1, 10, 20, 1),
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
        (1, 2, 20, 10, 10, 1 * 2 ** 32 + 10),
        (1, 2, 20, 20, 11, 2 * 2 ** 32 + 11),
        (1, 2, 10, 20, 12, 2 * 2 ** 32 + 12),
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


def _generate_some_indices(data, max_value_for_list):
    """
    Hypothesis helper that generates a list of some integers [0, `max_value_for_list`].
    The usage is to randomly sample some elements from a sequence of some element.
    """
    return data.draw(
        st.lists(
            st.integers(
                min_value=0,
                max_value=max_value_for_list,
            ),
        )
    )


@given(st.data())
def test_get_pubkey_for_indices(activated_genesis_validators, data):
    max_value_for_list = len(activated_genesis_validators) - 1
    indices = _generate_some_indices(data, max_value_for_list)
    pubkeys = get_pubkey_for_indices(activated_genesis_validators, indices)

    assert len(indices) == len(pubkeys)

    for index, pubkey in enumerate(pubkeys):
        validator_index = indices[index]
        assert activated_genesis_validators[validator_index].pubkey == pubkey


def _list_and_index(data, max_size=None, elements=st.integers()):
    """
    Hypothesis helper function cribbed from their docs on @composite
    """
    xs = data.draw(st.lists(elements, max_size=max_size, unique=True))
    i = data.draw(st.integers(min_value=0, max_value=max(len(xs) - 1, 0)))
    return (xs, i)


@given(st.data())
def test_generate_aggregate_pubkeys(activated_genesis_validators,
                                    sample_slashable_attestation_params,
                                    data):
    max_value_for_list = len(activated_genesis_validators) - 1
    (validator_indices, some_index) = _list_and_index(
        data,
        elements=st.integers(
            min_value=0,
            max_value=max_value_for_list,
        )
    )

    key = "validator_indices"
    sample_slashable_attestation_params[key] = validator_indices

    custody_bitfield = get_empty_bitfield(len(validator_indices))
    for index in range(some_index):
        custody_bitfield = set_voted(custody_bitfield, index)

    key = "custody_bitfield"
    sample_slashable_attestation_params[key] = custody_bitfield

    slashable_attestation = SlashableAttestation(**sample_slashable_attestation_params)
    custody_bit_0_indices, custody_bit_1_indices = slashable_attestation.custody_bit_indices
    assert len(
        set(custody_bit_0_indices).intersection(set(custody_bit_1_indices))
    ) == 0

    keys = generate_aggregate_pubkeys(activated_genesis_validators, slashable_attestation)
    assert len(keys) == 2

    (poc_0_key, poc_1_key) = keys

    poc_0_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_0_indices)
    poc_1_keys = get_pubkey_for_indices(activated_genesis_validators, custody_bit_1_indices)

    assert bls.aggregate_pubkeys(poc_0_keys) == poc_0_key
    assert bls.aggregate_pubkeys(poc_1_keys) == poc_1_key


def _get_indices_and_signatures(num_validators, message, privkeys, fork, epoch):
    num_indices = 5
    assert num_validators >= num_indices
    indices = random.sample(range(num_validators), num_indices)
    indices.sort()

    privkeys = [privkeys[i] for i in indices]
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        epoch=epoch,
        domain_type=domain_type,
    )
    signatures = tuple(
        map(lambda key: bls.sign(message, key, domain), privkeys)
    )
    return (indices, signatures)


def _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        params,
        messages,
        privkeys,
        fork):
    valid_params = copy.deepcopy(params)

    (validator_indices, signatures) = _get_indices_and_signatures(
        num_validators,
        messages[1],
        privkeys,
        fork,
        slot_to_epoch(params["data"].slot, epoch_length),
    )

    valid_params["validator_indices"] = validator_indices
    valid_params["custody_bitfield"] = get_empty_bitfield(len(validator_indices))

    aggregate_signature = bls.aggregate_signatures(signatures)

    valid_params["aggregate_signature"] = aggregate_signature

    return valid_params


def _corrupt_custody_bitfield_not_empty(params):
    validator_indices_length = len(params["validator_indices"])
    corrupt_custody_bitfield = get_empty_bitfield(validator_indices_length)
    corrupt_custody_bitfield = set_voted(corrupt_custody_bitfield, 0)
    return assoc(params, "custody_bitfield", corrupt_custody_bitfield)


def _corrupt_validator_indices(params):
    corrupt_validator_indices = (
        params["validator_indices"][1],
        params["validator_indices"][0],
    ) + tuple(params["validator_indices"][2:])

    return assoc(params, "validator_indices", corrupt_validator_indices)


def _corrupt_custody_bitfield_invalid(params):
    validator_indices_length = len(params["validator_indices"])
    corrupt_custody_bitfield = get_empty_bitfield(validator_indices_length + 8)
    return assoc(params, "custody_bitfield", corrupt_custody_bitfield)


def _corrupt_validator_indices_max(max_indices_per_slashable_vote, params):
    corrupt_validator_indices = [
        i
        for i in range(max_indices_per_slashable_vote + 1)
    ]
    return assoc(params, "validator_indices", corrupt_validator_indices)


def _corrupt_signature(epoch_length, params, fork):
    message = bytes.fromhex("deadbeefcafe")
    privkey = 42
    domain_type = SignatureDomain.DOMAIN_ATTESTATION
    domain = get_domain(
        fork=fork,
        epoch=slot_to_epoch(params["data"].slot, epoch_length),
        domain_type=domain_type,
    )
    corrupt_signature = bls.sign(message, privkey, domain)

    return assoc(params, "aggregate_signature", corrupt_signature)


def _create_slashable_attestation_messages(params):
    # TODO update when we move to `ssz` tree hash
    votes = SlashableAttestation(**params)
    return votes.messages


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_signature(
        epoch_length,
        num_validators,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**sample_fork_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    valid_votes = SlashableAttestation(**valid_params)
    assert verify_slashable_attestation_signature(state, valid_votes, epoch_length)

    invalid_params = _corrupt_signature(epoch_length, valid_params, state.fork)
    invalid_votes = SlashableAttestation(**invalid_params)
    assert not verify_slashable_attestation_signature(state, invalid_votes, epoch_length)


def _run_verify_slashable_vote(
        epoch_length,
        params,
        state,
        max_indices_per_slashable_vote,
        should_succeed):
    votes = SlashableAttestation(**params)
    if should_succeed:
        validate_slashable_attestation(state, votes, max_indices_per_slashable_vote, epoch_length)
    else:
        with pytest.raises(ValidationError):
            validate_slashable_attestation(
                state,
                votes,
                max_indices_per_slashable_vote,
                epoch_length,
            )


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
@pytest.mark.parametrize(
    (
        'param_mapper',
        'should_succeed',
        'needs_fork',
        'is_testing_max_length',
    ),
    [
        (lambda params: params, True, False, False),
        (_corrupt_custody_bitfield_not_empty, False, False, False),
        (_corrupt_validator_indices, False, False, False),
        (_corrupt_custody_bitfield_invalid, False, False, False),
        (_corrupt_validator_indices_max, False, False, True),
        (_corrupt_signature, False, True, False),
    ],
)
def test_validate_slashable_attestation(
        epoch_length,
        num_validators,
        param_mapper,
        should_succeed,
        needs_fork,
        is_testing_max_length,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params,
        max_indices_per_slashable_vote):
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**sample_fork_params),
    )

    # NOTE: we can do this before "correcting" the params as they
    # touch disjoint subsets of the provided params
    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    params = _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    if needs_fork:
        params = param_mapper(epoch_length, params, state.fork)
    elif is_testing_max_length:
        params = param_mapper(max_indices_per_slashable_vote, params)

    else:
        params = param_mapper(params)
    _run_verify_slashable_vote(
        epoch_length,
        params,
        state,
        max_indices_per_slashable_vote,
        should_succeed,
    )


@pytest.mark.parametrize(
    (
        'num_validators',
    ),
    [
        (40,),
    ]
)
def test_verify_slashable_attestation_after_fork(
        epoch_length,
        num_validators,
        privkeys,
        sample_beacon_state_params,
        activated_genesis_validators,
        genesis_balances,
        sample_slashable_attestation_params,
        sample_fork_params,
        max_indices_per_slashable_vote):
    # Test that slashable data is still valid after fork
    # Slashable data slot = 10, fork slot = 15, current slot = 20
    past_fork_params = {
        'previous_version': 0,
        'current_version': 1,
        'epoch': 15,
    }

    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        fork=Fork(**past_fork_params),
        slot=20,
    )

    messages = _create_slashable_attestation_messages(sample_slashable_attestation_params)

    valid_params = _correct_slashable_attestation_params(
        epoch_length,
        num_validators,
        sample_slashable_attestation_params,
        messages,
        privkeys,
        state.fork,
    )
    _run_verify_slashable_vote(
        epoch_length,
        valid_params,
        state,
        max_indices_per_slashable_vote,
        True,
    )


def test_is_double_vote(sample_attestation_data_params, epoch_length):
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

    assert is_double_vote(attestation_data_1, attestation_data_2, epoch_length)

    attestation_data_3_params = {
        **sample_attestation_data_params,
        'slot': 54321,
    }
    attestation_data_3 = AttestationData(**attestation_data_3_params)

    assert not is_double_vote(attestation_data_1, attestation_data_3, epoch_length)


@pytest.mark.parametrize(
    (
        'epoch_length,'
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
        # not (attestation_2_justified_epoch + 1 == attestation_2_slot)
        (1, 4, 0, 3, 1, False),
        # not (slot_to_epoch(attestation_2_slot) < slot_to_epoch(attestation_1_slot))
        (1, 4, 0, 4, 3, False),
        (1, 4, 0, 3, 2, True),
    ],
)
def test_is_surround_vote(sample_attestation_data_params,
                          epoch_length,
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

    assert is_surround_vote(attestation_data_1, attestation_data_2, epoch_length) == expected


def test_get_entry_exit_effect_epoch(entry_exit_delay):
    epoch = random.randint(0, FAR_FUTURE_EPOCH)
    entry_exit_effect_epoch = get_entry_exit_effect_epoch(
        epoch,
        entry_exit_delay,
    )
    assert entry_exit_effect_epoch == (epoch + 1 + entry_exit_delay)


def test_generate_seed(monkeypatch,
                       genesis_state,
                       epoch_length,
                       seed_lookahead,
                       entry_exit_delay,
                       latest_index_roots_length,
                       latest_randao_mixes_length):
    from eth2.beacon import helpers

    def mock_get_randao_mix(state,
                            epoch,
                            epoch_length,
                            latest_randao_mixes_length):
        return hash_eth2(
            state.root +
            abs(epoch).to_bytes(32, byteorder='big') +
            latest_randao_mixes_length.to_bytes(32, byteorder='big')
        )

    def mock_get_active_index_root(state,
                                   epoch,
                                   epoch_length,
                                   entry_exit_delay,
                                   latest_index_roots_length):
        return hash_eth2(
            state.root +
            abs(epoch).to_bytes(32, byteorder='big') +
            epoch_length.to_bytes(32, byteorder='big') +
            latest_index_roots_length.to_bytes(32, byteorder='big')
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

    seed = generate_seed(
        state=state,
        epoch=epoch,
        epoch_length=epoch_length,
        seed_lookahead=seed_lookahead,
        entry_exit_delay=entry_exit_delay,
        latest_index_roots_length=latest_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    assert seed == hash_eth2(
        mock_get_randao_mix(
            state=state,
            epoch=(epoch - seed_lookahead),
            epoch_length=epoch_length,
            latest_randao_mixes_length=latest_randao_mixes_length,
        ) + mock_get_active_index_root(
            state=state,
            epoch=epoch,
            epoch_length=epoch_length,
            entry_exit_delay=entry_exit_delay,
            latest_index_roots_length=latest_index_roots_length,
        )
    )
