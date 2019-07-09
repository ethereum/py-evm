import pytest

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth_utils.toolz import (
    assoc,
    curry,
)
import ssz

from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2._utils.bitfield import (
    set_voted,
    get_empty_bitfield,
)
from eth2._utils.hash import (
    hash_eth2,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
)
from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
    GWEI_PER_ETH,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_block_root,
    get_epoch_start_slot,
    get_delayed_activation_exit_epoch,
    get_randao_mix,
    slot_to_epoch,
)
from eth2.beacon.epoch_processing_helpers import (
    get_base_reward,
    get_effective_balance,
)
from eth2.beacon.datastructures.inclusion_info import InclusionInfo
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.eth1_data_vote import Eth1DataVote
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    _check_if_update_validator_registry,
    _compute_individual_penalty,
    _compute_total_penalties,
    _get_finalized_epoch,
    _is_epoch_justifiable,
    _is_majority_vote,
    _majority_threshold,
    _process_rewards_and_penalties_for_crosslinks,
    _process_rewards_and_penalties_for_finality,
    _update_eth1_vote_if_exists,
    _update_latest_active_index_roots,
    process_crosslinks,
    process_ejections,
    process_exit_queue,
    process_eth1_data_votes,
    process_final_updates,
    process_justification,
    process_slashings,
    process_validator_registry,
    update_validator_registry,
)

from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator


#
# Eth1 data votes
#
def test_majority_threshold(config):
    threshold = config.EPOCHS_PER_ETH1_VOTING_PERIOD * config.SLOTS_PER_EPOCH
    assert _majority_threshold(config) == threshold


@curry
def _mk_eth1_data_vote(params, vote_count):
    return Eth1DataVote(**assoc(params, "vote_count", vote_count))


def test_ensure_majority_votes(sample_eth1_data_vote_params, config):
    threshold = _majority_threshold(config)
    votes = map(_mk_eth1_data_vote(sample_eth1_data_vote_params), range(2 * threshold))
    for vote in votes:
        if vote.vote_count * 2 > threshold:
            assert _is_majority_vote(config, vote)
        else:
            assert not _is_majority_vote(config, vote)


def _some_bytes(seed):
    return hash_eth2(b'some_hash' + abs(seed).to_bytes(32, 'little'))


@pytest.mark.parametrize(
    (
        'vote_offsets'  # a tuple of offsets against the majority threshold
    ),
    (
        # no eth1_data_votes
        (),
        # a minority of eth1_data_votes (single)
        (-2,),
        # a plurality of eth1_data_votes (multiple but not majority)
        (-2, -2),
        # almost a majority!
        (0,),
        # a majority of eth1_data_votes
        (12,),
        # NOTE: we are accepting more than one block per slot if
        # there are multiple majorities so no need to test this
    )
)
def test_ensure_update_eth1_vote_if_exists(sample_beacon_state_params,
                                           config,
                                           vote_offsets):
    # one less than a majority is the majority divided by 2
    threshold = _majority_threshold(config) / 2
    data_votes = tuple(
        Eth1DataVote(
            eth1_data=Eth1Data(
                deposit_root=_some_bytes(offset),
                block_hash=_some_bytes(offset),
            ),
            vote_count=threshold + offset,
        ) for offset in vote_offsets
    )
    params = assoc(sample_beacon_state_params, "eth1_data_votes", data_votes)
    state = BeaconState(**params)

    if data_votes:  # we should have non-empty votes for non-empty inputs
        assert state.eth1_data_votes

    updated_state = _update_eth1_vote_if_exists(state, config)

    # we should *always* clear the pending set
    assert not updated_state.eth1_data_votes

    # we should update the 'latest' entry if we have a majority
    for offset in vote_offsets:
        if offset <= 0:
            assert state.latest_eth1_data == updated_state.latest_eth1_data
        else:
            assert len(data_votes) == 1  # sanity check
            assert updated_state.latest_eth1_data == data_votes[0].eth1_data


def test_only_process_eth1_data_votes_per_period(sample_beacon_state_params, config):
    slots_per_epoch = config.SLOTS_PER_EPOCH
    epochs_per_voting_period = config.EPOCHS_PER_ETH1_VOTING_PERIOD
    number_of_epochs_to_sample = 3

    # NOTE: we process if the _next_ epoch is on a voting period, so subtract 1 here
    # NOTE: we also avoid the epoch 0 so change range bounds
    epochs_to_process_votes = [
        (epochs_per_voting_period * epoch) - 1 for epoch in range(1, number_of_epochs_to_sample + 1)
    ]
    state = BeaconState(**sample_beacon_state_params)

    last_epoch_to_process_votes = epochs_to_process_votes[-1]
    # NOTE: we arbitrarily pick two after; if this fails here, think about how to
    # change so we avoid including another voting period
    some_epochs_after_last_target = last_epoch_to_process_votes + 2
    assert some_epochs_after_last_target % epochs_per_voting_period != 0

    for epoch in range(some_epochs_after_last_target):
        slot = get_epoch_start_slot(epoch, slots_per_epoch)
        state = state.copy(slot=slot)
        updated_state = process_eth1_data_votes(state, config)
        if epoch in epochs_to_process_votes:
            # we should get back a different state object
            assert id(state) != id(updated_state)
            # in particular, with no eth1 data votes
            assert not updated_state.eth1_data_votes
        else:
            # we get back the same state (by value)
            assert state == updated_state


#
# Justification
#
@pytest.mark.parametrize(
    "total_balance,"
    "current_epoch_boundary_attesting_balance,"
    "expected,",
    (
        (
            1500 * GWEI_PER_ETH, 1000 * GWEI_PER_ETH, True,
        ),
        (
            1500 * GWEI_PER_ETH, 999 * GWEI_PER_ETH, False,
        ),
    )
)
def test_is_epoch_justifiable(
        monkeypatch,
        sample_state,
        config,
        expected,
        total_balance,
        current_epoch_boundary_attesting_balance):
    current_epoch = 5

    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_get_total_balance(validators, epoch, max_deposit_amount):
        return total_balance

    def mock_get_epoch_boundary_attesting_balance(state, attestations, epoch, config):
        if epoch == current_epoch:
            return current_epoch_boundary_attesting_balance
        else:
            raise Exception("ensure mock is matching on a specific epoch")

    def mock_get_active_validator_indices(validator_registry, epoch):
        """
        Use this mock to ensure that `_is_epoch_justifiable` does not return early
        This is a bit unfortunate as it leaks an implementation detail, but we are
        already monkeypatching so we will see it through.
        """
        indices = tuple(range(3))
        # The only constraint on this mock is that the following assertion holds
        # We ensure the sustainability of this test by testing the invariant at runtime.
        assert indices
        return indices

    with monkeypatch.context() as m:
        m.setattr(
            epoch_processing,
            'get_total_balance',
            mock_get_total_balance,
        )
        m.setattr(
            epoch_processing,
            'get_epoch_boundary_attesting_balance',
            mock_get_epoch_boundary_attesting_balance,
        )
        m.setattr(
            epoch_processing,
            'get_active_validator_indices',
            mock_get_active_validator_indices,
        )

        epoch_justifiable = _is_epoch_justifiable(
            sample_state,
            sample_state.current_epoch_attestations,
            current_epoch,
            config,
        )

        assert epoch_justifiable == expected


@pytest.mark.parametrize(
    "justification_bitfield,"
    "previous_justified_epoch,"
    "current_justified_epoch,"
    "expected,",
    (
        # Rule 1
        (0b111110, 3, 3, (3, 1)),
        # Rule 2
        (0b111110, 4, 4, (4, 2)),
        # Rule 3
        (0b110111, 3, 4, (4, 3)),
        # Rule 4
        (0b110011, 2, 5, (5, 4)),
        # No finalize
        (0b110000, 2, 2, (1, 0)),
    )
)
def test_get_finalized_epoch(justification_bitfield,
                             previous_justified_epoch,
                             current_justified_epoch,
                             expected):
    previous_epoch = 5
    finalized_epoch = 1
    assert _get_finalized_epoch(justification_bitfield,
                                previous_justified_epoch,
                                current_justified_epoch,
                                finalized_epoch,
                                previous_epoch,) == expected


def test_justification_without_mock(sample_beacon_state_params,
                                    slots_per_historical_root,
                                    config):

    state = BeaconState(**sample_beacon_state_params).copy(
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(slots_per_historical_root)),
        justification_bitfield=0b0,
    )
    state = process_justification(state, config)
    assert state.justification_bitfield == 0b0


@pytest.mark.parametrize(
    (
        "genesis_slot,"
    ),
    [
        (0),
    ]
)
@pytest.mark.parametrize(
    # Each state contains epoch, current_epoch_justifiable, previous_epoch_justifiable,
    # previous_justified_epoch, current_justified_epoch,
    # justification_bitfield, and finalized_epoch.
    # Specify the last epoch processed state at the end of the items.
    "states,",
    (
        (
            # Trigger R4 to finalize epoch 1
            (0, True, False, 0, 0, 0b0, 0),
            (1, True, True, 0, 0, 0b1, 0),  # R4 finalize 0
            (2, True, True, 0, 1, 0b11, 0),  # R4 finalize 1
            (1, 2, 0b111, 1),
        ),
        (
            # Trigger R2 to finalize epoch 1
            # Trigger R3 to finalize epoch 2
            (2, False, True, 0, 1, 0b11, 0),  # R2 finalize 0
            (3, False, True, 1, 1, 0b110, 0),  # R2 finalize 1
            (4, True, True, 1, 2, 0b1110, 1),  # R3 finalize 2
            (2, 4, 0b11111, 2)
        ),
        (
            # Trigger R1 to finalize epoch 2
            (2, False, True, 0, 1, 0b11, 0),  # R2 finalize 0
            (3, False, True, 1, 1, 0b110, 0),  # R2 finalize 1
            (4, False, True, 1, 2, 0b1110, 1),  # R1 finalize 1
            (5, False, True, 2, 3, 0b11110, 1),  # R1 finalize 2
            (3, 4, 0b111110, 2)
        ),
    ),
)
def test_process_justification(monkeypatch,
                               config,
                               genesis_state,
                               states,
                               genesis_epoch=0):
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    for i in range(len(states) - 1):
        (
            current_epoch,
            current_epoch_justifiable,
            previous_epoch_justifiable,
            previous_justified_epoch_before,
            justified_epoch_before,
            justification_bitfield_before,
            finalized_epoch_before,
        ) = states[i]

        (
            previous_justified_epoch_after,
            justified_epoch_after,
            justification_bitfield_after,
            finalized_epoch_after,
        ) = states[i + 1][-4:]
        slot = (current_epoch + 1) * config.SLOTS_PER_EPOCH - 1

        def mock_is_epoch_justifiable(state, attestations, epoch, config):
            if epoch == current_epoch:
                return current_epoch_justifiable
            else:
                return previous_epoch_justifiable

        with monkeypatch.context() as m:
            m.setattr(
                epoch_processing,
                '_is_epoch_justifiable',
                mock_is_epoch_justifiable,
            )

            state = genesis_state.copy(
                slot=slot,
                previous_justified_epoch=previous_justified_epoch_before,
                current_justified_epoch=justified_epoch_before,
                justification_bitfield=justification_bitfield_before,
                finalized_epoch=finalized_epoch_before,
            )

            state = process_justification(state, config)

            assert state.previous_justified_epoch == previous_justified_epoch_after
            assert state.current_justified_epoch == justified_epoch_after
            assert state.justification_bitfield == justification_bitfield_after
            assert state.finalized_epoch == finalized_epoch_after


#
# Crosslink
#
@settings(
    max_examples=1,
    # Last CI run took >200ms. Allow up to 0.5s.
    deadline=500,
)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'genesis_slot,'
    ),
    [
        (
            90,
            10,
            9,
            10,
            0,
        ),
    ]
)
@pytest.mark.parametrize(
    (
        'success_crosslink_in_previous_epoch,'
        'success_crosslink_in_current_epoch,'
    ),
    [
        (
            False,
            False,
        ),
        (
            True,
            False,
        ),
        (
            False,
            True,
        ),
    ]
)
def test_process_crosslinks(
        random,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        success_crosslink_in_previous_epoch,
        success_crosslink_in_current_epoch,
        sample_attestation_data_params,
        sample_pending_attestation_record_params):
    shard = 1
    previous_epoch_crosslink_data_root = hash_eth2(b'previous_epoch_crosslink_data_root')
    current_epoch_crosslink_data_root = hash_eth2(b'current_epoch_crosslink_data_root')
    current_slot = config.SLOTS_PER_EPOCH * 2 - 1

    genesis_crosslinks = tuple([
        Crosslink(epoch=config.GENESIS_EPOCH, crosslink_data_root=ZERO_HASH32)
        for _ in range(shard_count)
    ])
    state = n_validators_state.copy(
        slot=current_slot,
        latest_crosslinks=genesis_crosslinks,
    )

    # Generate previous epoch attestations
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch = current_epoch - 1
    previous_epoch_start_slot = get_epoch_start_slot(previous_epoch, config.SLOTS_PER_EPOCH)
    current_epoch_start_slot = get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
    previous_epoch_attestations = []
    for slot_in_previous_epoch in range(previous_epoch_start_slot, current_epoch_start_slot):
        if len(previous_epoch_attestations) > 0:
            break
        for committee, _shard in get_crosslink_committees_at_slot(
            state,
            slot_in_previous_epoch,
            CommitteeConfig(config),
        ):
            if _shard == shard:
                # Sample validators attesting to this shard.
                # if `success_crosslink_in_previous_epoch` is True, have >2/3 committee attest
                if success_crosslink_in_previous_epoch:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 + 1))
                else:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 - 1))
                # Generate the bitfield
                aggregation_bitfield = get_empty_bitfield(len(committee))
                for v_index in attesting_validators:
                    aggregation_bitfield = set_voted(
                        aggregation_bitfield, committee.index(v_index))
                # Generate the attestation
                previous_epoch_attestations.append(
                    PendingAttestation(**sample_pending_attestation_record_params).copy(
                        aggregation_bitfield=aggregation_bitfield,
                        data=AttestationData(**sample_attestation_data_params).copy(
                            slot=slot_in_previous_epoch,
                            shard=shard,
                            crosslink_data_root=previous_epoch_crosslink_data_root,
                            previous_crosslink=Crosslink(
                                epoch=config.GENESIS_EPOCH,
                                crosslink_data_root=ZERO_HASH32,
                            ),
                        ),
                    )
                )

    # Generate current epoch attestations
    next_epoch_start_slot = current_epoch_start_slot + config.SLOTS_PER_EPOCH
    current_epoch_attestations = []
    for slot_in_current_epoch in range(current_epoch_start_slot, next_epoch_start_slot):
        if len(current_epoch_attestations) > 0:
            break
        for committee, _shard in get_crosslink_committees_at_slot(
            state,
            slot_in_current_epoch,
            CommitteeConfig(config),
        ):
            if _shard == shard:
                # Sample validators attesting to this shard.
                # if `success_crosslink_in_current_epoch` is True, have >2/3 committee attest
                if success_crosslink_in_current_epoch:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 + 1))
                else:
                    attesting_validators = random.sample(committee, (2 * len(committee) // 3 - 1))
                # Generate the bitfield
                aggregation_bitfield = get_empty_bitfield(len(committee))
                for v_index in attesting_validators:
                    aggregation_bitfield = set_voted(
                        aggregation_bitfield, committee.index(v_index))
                # Generate the attestation
                current_epoch_attestations.append(
                    PendingAttestation(**sample_pending_attestation_record_params).copy(
                        aggregation_bitfield=aggregation_bitfield,
                        data=AttestationData(**sample_attestation_data_params).copy(
                            slot=slot_in_current_epoch,
                            shard=shard,
                            crosslink_data_root=current_epoch_crosslink_data_root,
                            previous_crosslink=Crosslink(
                                epoch=config.GENESIS_EPOCH,
                                crosslink_data_root=ZERO_HASH32,
                            ),
                        ),
                    )
                )

    state = state.copy(
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )
    assert (state.latest_crosslinks[shard].epoch == config.GENESIS_EPOCH and
            state.latest_crosslinks[shard].crosslink_data_root == ZERO_HASH32)

    new_state = process_crosslinks(state, config)
    crosslink_record = new_state.latest_crosslinks[shard]
    if success_crosslink_in_current_epoch:
        attestation = current_epoch_attestations[0]
        assert (crosslink_record.epoch == current_epoch and
                crosslink_record.crosslink_data_root == attestation.data.crosslink_data_root and
                attestation.data.crosslink_data_root == current_epoch_crosslink_data_root)
    elif success_crosslink_in_previous_epoch:
        attestation = previous_epoch_attestations[0]
        assert (crosslink_record.epoch == current_epoch and
                crosslink_record.crosslink_data_root == attestation.data.crosslink_data_root and
                attestation.data.crosslink_data_root == previous_epoch_crosslink_data_root)
    else:
        assert (crosslink_record.epoch == config.GENESIS_EPOCH and
                crosslink_record.crosslink_data_root == ZERO_HASH32)


#
# Rewards and penalties
#
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'min_attestation_inclusion_delay,'
        'attestation_inclusion_reward_quotient,'
        'inactivity_penalty_quotient,'
        'genesis_slot,'
    ),
    [
        (
            15,
            3,
            5,
            3,
            1,
            4,
            10,
            0,
        )
    ]
)
@pytest.mark.parametrize(
    (
        'finalized_epoch,current_slot,'
        'penalized_validator_indices,'
        'previous_epoch_active_validator_indices,'
        'previous_epoch_attester_indices,'
        'previous_epoch_boundary_head_attester_indices,'
        'inclusion_distances,'
        'effective_balance,base_reward,'
        'expected_rewards_received'
    ),
    [
        (
            4, 15,  # epochs_since_finality <= 4
            {8, 9},
            {0, 1, 2, 3, 4, 5, 6, 7},
            {2, 3, 4, 5, 6},
            {2, 3, 4},
            {
                2: 1,
                3: 1,
                4: 1,
                5: 2,
                6: 3,
            },
            1000, 100,
            {
                0: -300,  # -3 * 100
                1: -275,  # -3 * 100 + 1 * 100 // 4
                2: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
                3: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
                4: 236,  # 100 * 5 // 8 + 100 * 3 // 8 + 100 * 3 // 8 + 100 * 1 // 1
                5: -63,  # 100 * 5 // 8 - 100 - 100 + 100 * 1 // 2 + 1 * 100 // 4
                6: -105,  # 100 * 5 // 8 - 100 - 100 + 100 * 1 // 3
                7: -300,  # -3 * 100
                8: 0,
                9: 0,
                10: 0,
                11: 0,
                12: 75,  # 3 * 100 // 4
                13: 0,
                14: 0,
            }
        ),
        (
            3, 23,  # epochs_since_finality > 4
            {8, 9},
            {0, 1, 2, 3, 4, 5, 6, 7},
            {2, 3, 4, 5, 6},
            {2, 3, 4},
            {
                2: 1,
                3: 1,
                4: 1,
                5: 2,
                6: 3,
            },
            1000, 100,
            {
                0: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
                1: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
                2: 0,  # -(100 - 100 * 1 // 1)
                3: 0,  # -(100 - 100 * 1 // 1)
                4: 0,  # -(100 - 100 * 1 // 1)
                5: -500,  # -(100 - 100 * 1 // 2) - (100 * 2 + 1000 * 5 // 10 // 2)
                6: -517,  # -(100 - 100 * 1 // 3) - (100 * 2 + 1000 * 5 // 10 // 2)
                7: -800,  # -2 * (100 + 1000 * 5 // 10 // 2) - 100
                8: -800,  # -(2 * (100 + 1000 * 5 // 10 // 2) + 100)
                9: -800,  # -(2 * (100 + 1000 * 5 // 10 // 2) + 100)
                10: 0,
                11: 0,
                12: 0,
                13: 0,
                14: 0,
            }
        ),
    ]
)
def test_process_rewards_and_penalties_for_finality(
        monkeypatch,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        min_attestation_inclusion_delay,
        inactivity_penalty_quotient,
        finalized_epoch,
        current_slot,
        penalized_validator_indices,
        previous_epoch_active_validator_indices,
        previous_epoch_attester_indices,
        previous_epoch_boundary_head_attester_indices,
        inclusion_distances,
        effective_balance,
        base_reward,
        expected_rewards_received,
        sample_pending_attestation_record_params,
        sample_attestation_data_params):
    # Mock `get_beacon_proposer_index
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_get_beacon_proposer_index(state,
                                       slot,
                                       committee_config,
                                       registry_change=False):
        mock_proposer_for_slot = {
            13: 12,
            14: 5,
            15: 1,
        }
        return mock_proposer_for_slot[slot]

    monkeypatch.setattr(
        epoch_processing,
        'get_beacon_proposer_index',
        mock_get_beacon_proposer_index
    )

    validator_registry = n_validators_state.validator_registry
    for index in penalized_validator_indices:
        validator_record = validator_registry[index].copy(
            slashed=True,
        )
        validator_registry = update_tuple_item(validator_registry, index, validator_record)
    state = n_validators_state.copy(
        slot=current_slot,
        finalized_epoch=finalized_epoch,
        validator_registry=validator_registry,
    )
    previous_total_balance = len(previous_epoch_active_validator_indices) * effective_balance

    attestation_slot = current_slot - slots_per_epoch
    inclusion_infos = {
        index: InclusionInfo(
            attestation_slot + inclusion_distances[index],
            attestation_slot,
        )
        for index in previous_epoch_attester_indices
    }

    effective_balances = {
        index: effective_balance
        for index in range(len(state.validator_registry))
    }

    base_rewards = {
        index: base_reward
        for index in range(len(state.validator_registry))
    }

    prev_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.SLOTS_PER_EPOCH), slots_per_epoch,
    )
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
    ]

    prev_epoch_attestations = []
    for i in range(slots_per_epoch):
        committee, shard = prev_epoch_crosslink_committees[i]
        participants_bitfield = get_empty_bitfield(target_committee_size)
        for index in previous_epoch_boundary_head_attester_indices:
            if index in committee:
                participants_bitfield = set_voted(participants_bitfield, committee.index(index))
        prev_epoch_attestations.append(
            PendingAttestation(**sample_pending_attestation_record_params).copy(
                aggregation_bitfield=participants_bitfield,
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=(prev_epoch_start_slot + i),
                    shard=shard,
                    target_root=get_block_root(
                        state,
                        prev_epoch_start_slot,
                        config.SLOTS_PER_HISTORICAL_ROOT,
                    ),
                    beacon_block_root=get_block_root(
                        state,
                        (prev_epoch_start_slot + i),
                        config.SLOTS_PER_HISTORICAL_ROOT,
                    ),
                ),
            )
        )
    state = state.copy(
        previous_epoch_attestations=prev_epoch_attestations,
    )

    rewards_received, penalties_received = _process_rewards_and_penalties_for_finality(
        state,
        config,
        previous_epoch_active_validator_indices,
        previous_total_balance,
        prev_epoch_attestations,
        previous_epoch_attester_indices,
        inclusion_infos,
        effective_balances,
        base_rewards,
    )

    for index in range(len(state.validator_registry)):
        assert (
            rewards_received[index] - penalties_received[index] == expected_rewards_received[index]
        )


@settings(
    max_examples=1,
    deadline=300,
)
@given(random=st.randoms())
@pytest.mark.parametrize(
    (
        'n,'
        'slots_per_epoch,'
        'target_committee_size,'
        'shard_count,'
        'current_slot,'
        'num_attesting_validators,'
        'genesis_slot,'
    ),
    [
        (
            50,
            10,
            5,
            10,
            100,
            3,
            0,
        ),
        (
            50,
            10,
            5,
            10,
            100,
            4,
            0,
        ),
    ]
)
def test_process_rewards_and_penalties_for_crosslinks(
        random,
        n_validators_state,
        config,
        slots_per_epoch,
        target_committee_size,
        shard_count,
        current_slot,
        num_attesting_validators,
        max_deposit_amount,
        min_attestation_inclusion_delay,
        sample_attestation_data_params,
        sample_pending_attestation_record_params):
    previous_epoch = current_slot // slots_per_epoch - 1
    state = n_validators_state.copy(
        slot=current_slot,
    )
    # Compute previous epoch committees
    prev_epoch_start_slot = get_epoch_start_slot(previous_epoch, slots_per_epoch)
    prev_epoch_crosslink_committees = [
        get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )[0] for slot in range(prev_epoch_start_slot, prev_epoch_start_slot + slots_per_epoch)
    ]

    # Record which validators attest during each slot for reward collation.
    each_slot_attestion_validators_list = []

    previous_epoch_attestations = []
    for i in range(slots_per_epoch):
        committee, shard = prev_epoch_crosslink_committees[i]
        # Randomly sample `num_attesting_validators` validators
        # from the committee to attest in this slot.
        crosslink_data_root_attesting_validators = random.sample(
            committee,
            num_attesting_validators,
        )
        each_slot_attestion_validators_list.append(crosslink_data_root_attesting_validators)
        participants_bitfield = get_empty_bitfield(target_committee_size)
        for index in crosslink_data_root_attesting_validators:
            participants_bitfield = set_voted(participants_bitfield, committee.index(index))
        data_slot = i + previous_epoch * slots_per_epoch
        previous_epoch_attestations.append(
            PendingAttestation(**sample_pending_attestation_record_params).copy(
                aggregation_bitfield=participants_bitfield,
                data=AttestationData(**sample_attestation_data_params).copy(
                    slot=data_slot,
                    shard=shard,
                    previous_crosslink=Crosslink(
                        epoch=config.GENESIS_EPOCH,
                        crosslink_data_root=ZERO_HASH32,
                    ),
                ),
                inclusion_slot=(data_slot + min_attestation_inclusion_delay),
            )
        )
    state = state.copy(
        previous_epoch_attestations=tuple(previous_epoch_attestations),
    )

    active_validators = set(
        [
            i for i in range(len(state.validator_registry))
        ]
    )

    effective_balances = {
        index: get_effective_balance(
            state.validator_balances,
            index,
            config.MAX_DEPOSIT_AMOUNT,
        )
        for index in active_validators
    }

    validator_balance = max_deposit_amount
    total_active_balance = len(active_validators) * validator_balance

    base_rewards = {
        index: get_base_reward(
            state=state,
            index=index,
            base_reward_quotient=config.BASE_REWARD_QUOTIENT,
            previous_total_balance=total_active_balance,
            max_deposit_amount=max_deposit_amount,
        )
        for index in active_validators
    }

    rewards_received, penalties_received = _process_rewards_and_penalties_for_crosslinks(
        state,
        config,
        effective_balances,
        base_rewards,
    )

    expected_rewards_received = {
        index: 0
        for index in range(len(state.validator_registry))
    }
    for i in range(slots_per_epoch):
        crosslink_committee, shard = prev_epoch_crosslink_committees[i]
        attesting_validators = each_slot_attestion_validators_list[i]
        total_attesting_balance = len(attesting_validators) * validator_balance
        total_committee_balance = len(crosslink_committee) * validator_balance
        for index in attesting_validators:
            reward = get_base_reward(
                state=state,
                index=index,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                previous_total_balance=total_active_balance,
                max_deposit_amount=max_deposit_amount,
            ) * total_attesting_balance // total_committee_balance
            expected_rewards_received[index] += reward
        for index in set(crosslink_committee).difference(attesting_validators):
            penalty = get_base_reward(
                state=state,
                index=index,
                base_reward_quotient=config.BASE_REWARD_QUOTIENT,
                previous_total_balance=total_active_balance,
                max_deposit_amount=max_deposit_amount,
            )
            expected_rewards_received[index] -= penalty

    # Check the rewards/penalties match
    for index in range(len(state.validator_registry)):
        assert (
            rewards_received[index] - penalties_received[index] == expected_rewards_received[index]
        )


#
# Ejections
#
@pytest.mark.parametrize(
    (
        'genesis_slot,'
    ),
    [
        (0),
    ]
)
def test_process_ejections(genesis_state, config, activation_exit_delay):
    current_epoch = 8
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH),
    )
    delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(
        current_epoch,
        activation_exit_delay,
    )

    ejecting_validator_index = 0
    validator = state.validator_registry[ejecting_validator_index]
    assert validator.is_active(current_epoch)
    assert validator.exit_epoch > delayed_activation_exit_epoch

    state = state.update_validator_balance(
        validator_index=ejecting_validator_index,
        balance=config.EJECTION_BALANCE - 1,
    )
    result_state = process_ejections(state, config)
    result_validator = result_state.validator_registry[ejecting_validator_index]
    assert result_validator.is_active(current_epoch)
    assert result_validator.exit_epoch == delayed_activation_exit_epoch
    # The ejecting validator will be inactive at the exit_epoch
    assert not result_validator.is_active(result_validator.exit_epoch)
    # Other validators are not ejected
    assert (
        result_state.validator_registry[ejecting_validator_index + 1].exit_epoch ==
        FAR_FUTURE_EPOCH
    )


#
# Validator registry and shuffling seed data
#
@pytest.mark.parametrize(
    (
        'num_validators, slots_per_epoch, target_committee_size, shard_count, state_slot,'
        'validator_registry_update_epoch,'
        'finalized_epoch,'
        'has_crosslink,'
        'crosslink_epoch,'
        'expected_need_to_update,'
    ),
    [
        # state.finalized_epoch <= state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 4, False, 0, False
        ),
        # state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 8, True, 4, False,
        ),
        # state.finalized_epoch > state.validator_registry_update_epoch and
        # state.latest_crosslinks[shard].epoch > state.validator_registry_update_epoch
        (
            40, 4, 2, 2, 16,
            4, 8, True, 6, True,
        ),
    ]
)
def test_check_if_update_validator_registry(genesis_state,
                                            state_slot,
                                            validator_registry_update_epoch,
                                            finalized_epoch,
                                            has_crosslink,
                                            crosslink_epoch,
                                            expected_need_to_update,
                                            config):
    state = genesis_state.copy(
        slot=state_slot,
        finalized_epoch=finalized_epoch,
        validator_registry_update_epoch=validator_registry_update_epoch,
    )
    if has_crosslink:
        crosslink = Crosslink(
            epoch=crosslink_epoch,
            crosslink_data_root=ZERO_HASH32,
        )
        latest_crosslinks = state.latest_crosslinks
        for shard in range(config.SHARD_COUNT):
            latest_crosslinks = update_tuple_item(
                latest_crosslinks,
                shard,
                crosslink,
            )
        state = state.copy(
            latest_crosslinks=latest_crosslinks,
        )

    need_to_update, num_shards_in_committees = _check_if_update_validator_registry(state, config)

    assert need_to_update == expected_need_to_update
    if expected_need_to_update:
        expected_num_shards_in_committees = get_current_epoch_committee_count(
            state,
            shard_count=config.SHARD_COUNT,
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            target_committee_size=config.TARGET_COMMITTEE_SIZE,
        )
        assert num_shards_in_committees == expected_num_shards_in_committees
    else:
        assert num_shards_in_committees == 0


@pytest.mark.parametrize(
    (
        'n',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (
            10,
            10,
            9,
            10,
        ),
    ]
)
def test_update_validator_registry(n,
                                   n_validators_state,
                                   config,
                                   slots_per_epoch):
    validator_registry = list(n_validators_state.validator_registry)
    activating_index = n
    exiting_index = 0

    activating_validator = Validator.create_pending_validator(
        pubkey=b'\x10' * 48,
        withdrawal_credentials=b'\x11' * 32,
    )

    exiting_validator = n_validators_state.validator_registry[exiting_index].copy(
        exit_epoch=FAR_FUTURE_EPOCH,
        initiated_exit=True,
    )

    validator_registry[exiting_index] = exiting_validator
    validator_registry.append(activating_validator)
    state = n_validators_state.copy(
        validator_registry=validator_registry,
        validator_balances=n_validators_state.validator_balances + (config.MAX_DEPOSIT_AMOUNT,),
    )

    state = update_validator_registry(state, config)

    entry_exit_effect_epoch = get_delayed_activation_exit_epoch(
        state.current_epoch(slots_per_epoch),
        config.ACTIVATION_EXIT_DELAY,
    )

    # Check if the activating_validator is activated
    assert state.validator_registry[activating_index].activation_epoch == entry_exit_effect_epoch
    # Check if the activating_validator is exited
    assert state.validator_registry[exiting_index].exit_epoch == entry_exit_effect_epoch


@pytest.mark.parametrize(
    (
        'num_validators, slots_per_epoch, target_committee_size, shard_count,'
        'latest_randao_mixes_length, min_seed_lookahead, state_slot,'
        'need_to_update,'
        'num_shards_in_committees,'
        'validator_registry_update_epoch,'
        'epochs_since_last_registry_change_is_power_of_two,'
        'current_shuffling_epoch,'
        'latest_randao_mixes,'
        'expected_current_shuffling_epoch,'
    ),
    [
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            2,
            True,  # (state.current_epoch - state.validator_registry_update_epoch) is power of two
            0,
            [i.to_bytes(32, 'little') for i in range(2**10)],
            5,  # expected current_shuffling_epoch is state.next_epoch
        ),
        (
            40, 4, 2, 2,
            2**10, 4, 19,
            False,
            10,
            1,
            False,  # (state.current_epoch - state.validator_registry_update_epoch) != power of two
            0,
            [i.to_bytes(32, 'little') for i in range(2**10)],
            0,  # expected_current_shuffling_epoch is current_shuffling_epoch because it will not be updated  # noqa: E501
        ),
    ]
)
def test_process_validator_registry(monkeypatch,
                                    genesis_state,
                                    slots_per_epoch,
                                    state_slot,
                                    need_to_update,
                                    num_shards_in_committees,
                                    validator_registry_update_epoch,
                                    epochs_since_last_registry_change_is_power_of_two,
                                    current_shuffling_epoch,
                                    latest_randao_mixes,
                                    expected_current_shuffling_epoch,
                                    activation_exit_delay,
                                    config):
    # Mock check_if_update_validator_registry
    from eth2.beacon.state_machines.forks.serenity import epoch_processing

    def mock_check_if_update_validator_registry(state, config):
        return need_to_update, num_shards_in_committees

    monkeypatch.setattr(
        epoch_processing,
        '_check_if_update_validator_registry',
        mock_check_if_update_validator_registry
    )

    # Mock generate_seed
    new_seed = b'\x88' * 32

    def mock_generate_seed(state,
                           epoch,
                           committee_config):
        return new_seed

    monkeypatch.setattr(
        'eth2.beacon.helpers.generate_seed',
        mock_generate_seed
    )

    # Set state
    state = genesis_state.copy(
        slot=state_slot,
        validator_registry_update_epoch=validator_registry_update_epoch,
        current_shuffling_epoch=current_shuffling_epoch,
        latest_randao_mixes=latest_randao_mixes,
    )

    result_state = process_validator_registry(state, config)

    assert result_state.previous_shuffling_epoch == state.current_shuffling_epoch
    assert result_state.previous_shuffling_start_shard == state.current_shuffling_start_shard
    assert result_state.previous_shuffling_seed == state.current_shuffling_seed

    if need_to_update:
        assert result_state.current_shuffling_epoch == slot_to_epoch(state_slot, slots_per_epoch)
        assert result_state.current_shuffling_seed == new_seed
        # TODO: Add test for validator registry updates
    else:
        assert (
            result_state.current_shuffling_epoch ==
            expected_current_shuffling_epoch
        )
        # state.current_shuffling_start_shard is left unchanged.
        assert result_state.current_shuffling_start_shard == state.current_shuffling_start_shard

        if epochs_since_last_registry_change_is_power_of_two:
            assert result_state.current_shuffling_seed == new_seed
        else:
            assert result_state.current_shuffling_seed != new_seed


@pytest.mark.parametrize(
    (
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'latest_slashed_exit_length',
        'latest_slashed_balances',
        'expected_total_penalties',
    ),
    [
        (4, 8, 8, 8, (30, 10) + (0,) * 6, 30 - 10)
    ]
)
def test_compute_total_penalties(genesis_state,
                                 config,
                                 slots_per_epoch,
                                 current_epoch,
                                 latest_slashed_balances,
                                 expected_total_penalties):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
        latest_slashed_balances=latest_slashed_balances,
    )
    total_penalties = _compute_total_penalties(
        state,
        config,
        current_epoch,
    )
    assert total_penalties == expected_total_penalties


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'latest_slashed_exit_length',
    ),
    [
        (
            10, 4, 8, 8, 8,
        )
    ]
)
@pytest.mark.parametrize(
    (
        'total_penalties',
        'total_balance',
        'min_penalty_quotient',
        'expected_penalty',
    ),
    [
        (
            10**9,  # 1 ETH
            (32 * 10**9 * 10),
            2**5,
            # effective_balance // MIN_PENALTY_QUOTIENT,
            32 * 10**9 // 2**5,
        ),
        (
            10**9,  # 1 ETH
            (32 * 10**9 * 10),
            2**10,  # Make MIN_PENALTY_QUOTIENT greater
            # effective_balance * min(total_penalties * 3, total_balance) // total_balance,
            32 * 10**9 * min(10**9 * 3, (32 * 10**9 * 10)) // (32 * 10**9 * 10),
        ),
    ]
)
def test_compute_individual_penalty(genesis_state,
                                    config,
                                    slots_per_epoch,
                                    current_epoch,
                                    latest_slashed_exit_length,
                                    total_penalties,
                                    total_balance,
                                    expected_penalty):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
    )
    validator_index = 0
    penalty = _compute_individual_penalty(
        state=state,
        config=config,
        validator_index=validator_index,
        total_penalties=total_penalties,
        total_balance=total_balance,
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'latest_slashed_exit_length',
        'latest_slashed_balances',
        'expected_penalty',
    ),
    [
        (
            10,
            4,
            8,
            8,
            8,
            (2 * 10**9, 10**9) + (0,) * 6,
            32 * 10**9 // 2**5,
        ),
    ]
)
def test_process_slashings(genesis_state,
                           config,
                           current_epoch,
                           latest_slashed_balances,
                           slots_per_epoch,
                           latest_slashed_exit_length,
                           expected_penalty):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
        latest_slashed_balances=latest_slashed_balances,
    )
    slashing_validator_index = 0
    validator = state.validator_registry[slashing_validator_index].copy(
        slashed=True,
        withdrawable_epoch=current_epoch + latest_slashed_exit_length // 2
    )
    state = state.update_validator_registry(slashing_validator_index, validator)

    result_state = process_slashings(state, config)
    penalty = (
        state.validator_balances[slashing_validator_index] -
        result_state.validator_balances[slashing_validator_index]
    )
    assert penalty == expected_penalty


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
    ),
    [
        (10, 4, 8, 8)
    ]
)
@pytest.mark.parametrize(
    (
        'min_validator_withdrawability_delay',
        'withdrawable_epoch',
        'exit_epoch',
        'is_eligible',
    ),
    [
        # current_epoch == validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        (4, FAR_FUTURE_EPOCH, 4, True),
        # withdrawable_epoch != FAR_FUTURE_EPOCH
        (4, 8, 4, False),
        # current_epoch < validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        (4, FAR_FUTURE_EPOCH, 5, False),
    ]
)
def test_process_exit_queue_eligible(genesis_state,
                                     config,
                                     current_epoch,
                                     min_validator_withdrawability_delay,
                                     withdrawable_epoch,
                                     exit_epoch,
                                     is_eligible):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
    )
    validator_index = 0

    # Set eligible validators
    state = state.update_validator_registry(
        validator_index,
        state.validator_registry[validator_index].copy(
            withdrawable_epoch=withdrawable_epoch,
            exit_epoch=exit_epoch,
        )
    )

    result_state = process_exit_queue(state, config)

    if is_eligible:
        # Check if they got prepared for withdrawal
        assert (
            result_state.validator_registry[validator_index].withdrawable_epoch ==
            current_epoch + min_validator_withdrawability_delay
        )
    else:
        assert (
            result_state.validator_registry[validator_index].withdrawable_epoch ==
            state.validator_registry[validator_index].withdrawable_epoch
        )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'genesis_slot',
        'current_epoch',
        'min_validator_withdrawability_delay'
    ),
    [
        (10, 4, 4, 16, 4)
    ]
)
@pytest.mark.parametrize(
    (
        'max_exit_dequeues_per_epoch',
        'num_eligible_validators',
        'validator_exit_epochs',
    ),
    [
        # no  eligible validator
        (4, 0, ()),
        # max_exit_dequeues_per_epoch == num_eligible_validators
        (4, 4, (4, 5, 6, 7)),
        # max_exit_dequeues_per_epoch > num_eligible_validators
        (5, 4, (4, 5, 6, 7)),
        # max_exit_dequeues_per_epoch < num_eligible_validators
        (3, 4, (4, 5, 6, 7)),
        (3, 4, (7, 6, 5, 4)),
    ]
)
def test_process_exit_queue(genesis_state,
                            config,
                            current_epoch,
                            num_validators,
                            max_exit_dequeues_per_epoch,
                            min_validator_withdrawability_delay,
                            num_eligible_validators,
                            validator_exit_epochs):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, config.SLOTS_PER_EPOCH)
    )

    # Set eligible validators
    assert num_eligible_validators <= num_validators
    for i in range(num_eligible_validators):
        state = state.update_validator_registry(
            i,
            state.validator_registry[i].copy(
                exit_epoch=validator_exit_epochs[i],
            )
        )

    result_state = process_exit_queue(state, config)

    # Exit queue is sorted
    sorted_indices = sorted(
        range(num_eligible_validators),
        key=lambda i: validator_exit_epochs[i],
    )
    filtered_indices = sorted_indices[:min(max_exit_dequeues_per_epoch, num_eligible_validators)]

    for i in range(num_validators):
        if i in set(filtered_indices):
            # Check if they got prepared for withdrawal
            assert (
                result_state.validator_registry[i].withdrawable_epoch ==
                current_epoch + min_validator_withdrawability_delay
            )
        else:
            assert (
                result_state.validator_registry[i].withdrawable_epoch ==
                FAR_FUTURE_EPOCH
            )


#
# Final updates
#
@pytest.mark.parametrize(
    (
        'slots_per_epoch,'
        'latest_active_index_roots_length,'
        'state_slot,'
    ),
    [
        (4, 16, 4),
        (4, 16, 64),
    ]
)
def test_update_latest_active_index_roots(genesis_state,
                                          committee_config,
                                          state_slot,
                                          slots_per_epoch,
                                          latest_active_index_roots_length,
                                          activation_exit_delay):
    state = genesis_state.copy(
        slot=state_slot,
    )

    result_state = _update_latest_active_index_roots(state, committee_config)

    index_root = ssz.hash_tree_root(
        get_active_validator_indices(
            state.validator_registry,
            slot_to_epoch(state.slot, slots_per_epoch),
        ),
        ssz.sedes.List(ssz.uint64),
    )

    target_epoch = state.next_epoch(slots_per_epoch) + activation_exit_delay
    assert result_state.latest_active_index_roots[
        target_epoch % latest_active_index_roots_length
    ] == index_root


@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch'
    ),
    [
        (10, 4),
    ]
)
def test_process_final_updates(genesis_state,
                               config,
                               sample_attestation_params):
    current_slot = 10
    state = genesis_state.copy(
        slot=current_slot,
    )
    current_index = state.next_epoch(config.SLOTS_PER_EPOCH) % config.LATEST_SLASHED_EXIT_LENGTH
    previous_index = state.current_epoch(config.SLOTS_PER_EPOCH) % config.LATEST_SLASHED_EXIT_LENGTH

    attestation = Attestation(**sample_attestation_params)
    previous_epoch_attestation_slot = current_slot - config.SLOTS_PER_EPOCH
    num_previous_epoch_attestations = 2
    previous_epoch_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=previous_epoch_attestation_slot
            )
        )
        for _ in range(num_previous_epoch_attestations)
    ]
    num_current_epoch_attestations = 3
    current_epoch_attestations = [
        attestation.copy(
            data=attestation.data.copy(
                slot=current_slot
            )
        )
        for _ in range(num_current_epoch_attestations)
    ]

    # Fill latest_slashed_balances
    slashed_balance_of_previous_epoch = 100
    latest_slashed_balances = update_tuple_item(
        state.latest_slashed_balances,
        previous_index,
        slashed_balance_of_previous_epoch,
    )
    state = state.copy(
        latest_slashed_balances=latest_slashed_balances,
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )

    result_state = process_final_updates(state, config)

    assert (
        (
            result_state.latest_slashed_balances[current_index] ==
            slashed_balance_of_previous_epoch
        ) and (
            result_state.latest_randao_mixes[current_index] == get_randao_mix(
                state=state,
                epoch=state.current_epoch(config.SLOTS_PER_EPOCH),
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            )
        )
    )

    for attestation in result_state.previous_epoch_attestations:
        assert attestation.data.slot == current_slot
    assert len(result_state.current_epoch_attestations) == 0
