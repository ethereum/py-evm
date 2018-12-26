import pytest

from eth_utils import (
    denoms,
    ValidationError,
)

from eth.constants import (
    ZERO_HASH32,
)


from eth.beacon.enums import (
    ValidatorStatusCode,
)
from eth.beacon.types.attestation_data import (
    AttestationData,
)
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.fork_data import ForkData
from eth.beacon.types.shard_committees import ShardCommittee
from eth.beacon.types.states import BeaconState
from eth.beacon.types.validator_records import ValidatorRecord
from eth.beacon.helpers import (
    _get_element_from_recent_list,
    get_active_validator_indices,
    get_attestation_participants,
    get_beacon_proposer_index,
    get_block_root,
    get_effective_balance,
    get_domain,
    get_fork_version,
    get_new_shuffling,
    get_new_validator_registry_delta_chain_tip,
    _get_shard_committees_at_slot,
    get_block_committees_info,
    is_double_vote,
    is_surround_vote,
)


from tests.beacon.helpers import (
    get_pseudo_chain,
)


@pytest.fixture()
def sample_block(sample_beacon_block_params):
    return BaseBeaconBlock(**sample_beacon_block_params)


@pytest.fixture()
def sample_state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


def get_sample_shard_committees_at_slots(num_slot,
                                         num_shard_committee_per_slot,
                                         sample_shard_committee_params):

    return tuple(
        [
            [
                ShardCommittee(**sample_shard_committee_params)
                for _ in range(num_shard_committee_per_slot)
            ]
            for _ in range(num_slot)
        ]
    )


def generate_mock_latest_block_roots(
        genesis_block,
        current_block_number,
        epoch_length):
    chain_length = (current_block_number // epoch_length + 1) * epoch_length
    blocks = get_pseudo_chain(chain_length, genesis_block)
    latest_block_roots = [
        b'\x00' * 32
        for i
        in range(epoch_length * 2 - current_block_number)
    ] + [block.root for block in blocks[:current_block_number]]
    return blocks, latest_block_roots


@pytest.mark.parametrize(
    (
        'target_list,target_slot,slot_relative_position,result'
    ),
    [
        ([i for i in range(5)], 10, 7, 3),
        ([], 1, 1, ValueError()),
        # target_slot < slot_relative_position
        ([i for i in range(5)], 1, 2, ValueError()),
        # target_slot >= slot_relative_position + target_list_length
        ([i for i in range(5)], 6, 1, ValueError()),
    ],
)
def test_get_element_from_recent_list(target_list,
                                      target_slot,
                                      slot_relative_position,
                                      result):
    if isinstance(result, Exception):
        with pytest.raises(ValueError):
            _get_element_from_recent_list(
                target_list,
                target_slot,
                slot_relative_position,
            )
    else:
        assert result == _get_element_from_recent_list(
            target_list,
            target_slot,
            slot_relative_position,
        )


#
# Get block rootes
#
@pytest.mark.parametrize(
    (
        'current_block_number,target_slot,success'
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
def test_get_block_root(current_block_number,
                        target_slot,
                        success,
                        epoch_length,
                        sample_block):
    blocks, latest_block_roots = generate_mock_latest_block_roots(
        sample_block,
        current_block_number,
        epoch_length,
    )

    if success:
        block_root = get_block_root(
            latest_block_roots,
            current_block_number,
            target_slot,
        )
        assert block_root == blocks[target_slot].root
    else:
        with pytest.raises(ValueError):
            get_block_root(
                latest_block_roots,
                current_block_number,
                target_slot,
            )


#
# Get shards_committees or indices
#
@pytest.mark.parametrize(
    (
        'num_validators,'
        'cycle_length,'
        'state_slot,'
        'num_slot,'
        'num_shard_committee_per_slot,'
        'slot,'
        'success'
    ),
    [
        (
            100,
            64,
            0,
            128,
            10,
            0,
            True,
        ),
        (
            100,
            64,
            64,
            128,
            10,
            64,
            True,
        ),
        # The length of shard_committees_at_slots != epoch_length * 2
        (
            100,
            64,
            64,
            127,
            10,
            0,
            False,
        ),
        # slot is too small
        (
            100,
            64,
            128,
            128,
            10,
            0,
            False,
        ),
        # slot is too large
        (
            100,
            64,
            0,
            128,
            10,
            64,
            False,
        ),
    ],
)
def test_get_shard_committees_at_slot(
        num_validators,
        cycle_length,
        state_slot,
        num_slot,
        num_shard_committee_per_slot,
        slot,
        success,
        epoch_length,
        sample_shard_committee_params):

    shard_committees_at_slots = get_sample_shard_committees_at_slots(
        num_slot,
        num_shard_committee_per_slot,
        sample_shard_committee_params
    )

    if success:
        shard_committees = _get_shard_committees_at_slot(
            state_slot=state_slot,
            shard_committees_at_slots=shard_committees_at_slots,
            slot=slot,
            epoch_length=epoch_length,
        )
        assert len(shard_committees) > 0
        assert len(shard_committees[0].committee) > 0
    else:
        with pytest.raises(ValueError):
            _get_shard_committees_at_slot(
                state_slot=state_slot,
                shard_committees_at_slots=shard_committees_at_slots,
                slot=slot,
                epoch_length=epoch_length,
            )


#
# Shuffling
#
@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count'
    ),
    [
        (1000, 20, 10, 100),
        (100, 50, 10, 10),
        (20, 10, 3, 10),  # active_validators_size < epoch_length * target_committee_size
    ],
)
def test_get_new_shuffling_is_complete(genesis_validators,
                                       epoch_length,
                                       target_committee_size,
                                       shard_count):
    shuffling = get_new_shuffling(
        seed=b'\x35' * 32,
        validators=genesis_validators,
        crosslinking_start_shard=0,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    assert len(shuffling) == epoch_length
    validators = set()
    shards = set()
    for slot_indices in shuffling:
        for shard_committee in slot_indices:
            shards.add(shard_committee.shard)
            for validator_index in shard_committee.committee:
                validators.add(validator_index)

    assert len(validators) == len(genesis_validators)


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count'
    ),
    [
        (1000, 20, 10, 100),
        (100, 50, 10, 10),
        (20, 10, 3, 10),
    ],
)
def test_get_new_shuffling_handles_shard_wrap(genesis_validators,
                                              epoch_length,
                                              target_committee_size,
                                              shard_count):
    shuffling = get_new_shuffling(
        seed=b'\x35' * 32,
        validators=genesis_validators,
        crosslinking_start_shard=shard_count - 1,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    # shard assignments should wrap around to 0 rather than continuing to SHARD_COUNT
    for slot_indices in shuffling:
        for shard_committee in slot_indices:
            assert shard_committee.shard < shard_count


#
# Get proposer postition
#
@pytest.mark.parametrize(
    (
        'num_validators,committee,parent_block_number,result_proposer_index'
    ),
    [
        (100, [4, 5, 6, 7], 0, 4),
        (100, [4, 5, 6, 7], 2, 6),
        (100, [4, 5, 6, 7], 11, 7),
        (100, [], 1, ValidationError()),
    ],
)
def test_get_block_committees_info(monkeypatch,
                                   sample_block,
                                   sample_state,
                                   num_validators,
                                   committee,
                                   parent_block_number,
                                   result_proposer_index,
                                   epoch_length):
    from eth.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=1,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_shard_committees_at_slot',
        mock_get_shard_committees_at_slot
    )

    parent_block = sample_block
    parent_block = sample_block.copy(
        slot=parent_block_number,
    )

    if isinstance(result_proposer_index, Exception):
        with pytest.raises(ValidationError):
            get_block_committees_info(
                parent_block,
                sample_state,
                epoch_length,
            )
    else:
        block_committees_info = get_block_committees_info(
            parent_block,
            sample_state,
            epoch_length,
        )
        assert (
            block_committees_info.proposer_index ==
            result_proposer_index
        )


@pytest.mark.parametrize(
    (
        'num_validators,'
        'cycle_length,'
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
        cycle_length,
        committee,
        slot,
        success,
        epoch_length,
        sample_state):

    from eth.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=1,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_shard_committees_at_slot',
        mock_get_shard_committees_at_slot
    )
    if success:
        proposer_index = get_beacon_proposer_index(
            sample_state,
            slot,
            epoch_length
        )
        assert proposer_index == committee[slot % len(committee)]
    else:
        with pytest.raises(ValidationError):
            get_beacon_proposer_index(
                sample_state,
                slot,
                epoch_length
            )


def test_get_active_validator_indices(sample_validator_record_params):
    # 3 validators are ACTIVE
    validators = [
        ValidatorRecord(
            **sample_validator_record_params,
        ).copy(
            status=ValidatorStatusCode.ACTIVE,
        )
        for i in range(3)
    ]
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 3

    # Make one validator becomes ACTIVE_PENDING_EXIT.
    validators[0] = validators[0].copy(
        status=ValidatorStatusCode.ACTIVE_PENDING_EXIT,
    )
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 3

    # Make one validator becomes EXITED_WITHOUT_PENALTY.
    validators[0] = validators[0].copy(
        status=ValidatorStatusCode.EXITED_WITHOUT_PENALTY,
    )
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 2


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'committee,'
        'participation_bitfield,'
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
        participation_bitfield,
        expected,
        sample_state):
    from eth.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=0,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_shard_committees_at_slot',
        mock_get_shard_committees_at_slot
    )

    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            get_attestation_participants(
                state=sample_state,
                slot=0,
                shard=0,
                participation_bitfield=participation_bitfield,
                epoch_length=epoch_length,
            )
    else:
        result = get_attestation_participants(
            state=sample_state,
            slot=0,
            shard=0,
            participation_bitfield=participation_bitfield,
            epoch_length=epoch_length,
        )

        assert result == expected


@pytest.mark.parametrize(
    (
        'balance,'
        'max_deposit,'
        'expected'
    ),
    [
        (
            1 * denoms.gwei,
            32,
            1 * denoms.gwei,
        ),
        (
            32 * denoms.gwei,
            32,
            32 * denoms.gwei,
        ),
        (
            33 * denoms.gwei,
            32,
            32 * denoms.gwei,
        )
    ]
)
def test_get_effective_balance(balance, max_deposit, expected, sample_validator_record_params):
    validator = ValidatorRecord(**sample_validator_record_params).copy(
        balance=balance,
    )
    result = get_effective_balance(validator, max_deposit)
    assert result == expected


@pytest.mark.parametrize(
    (
        'validator_index,'
        'pubkey,'
        'flag,'
        'expected'
    ),
    [
        (
            1,
            2 * 256 - 1,
            1,
            b'\xb8K\xad[zDE\xef\x00Z\x9c\x04\xdc\x95\xff\x9c\xeaP\x15\xf5\xfb\xdd\x0f\x1c:\xd7U+\x81\x92:\xee'  # noqa: E501
        ),
    ]
)
def test_get_new_validator_registry_delta_chain_tip(validator_index,
                                                    pubkey,
                                                    flag,
                                                    expected):
    result = get_new_validator_registry_delta_chain_tip(
        current_validator_registry_delta_chain_tip=ZERO_HASH32,
        validator_index=validator_index,
        pubkey=pubkey,
        flag=flag,
    )
    assert result == expected


@pytest.mark.parametrize(
    (
        'pre_fork_version,'
        'post_fork_version,'
        'fork_slot,'
        'current_slot,'
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
def test_get_fork_version(pre_fork_version,
                          post_fork_version,
                          fork_slot,
                          current_slot,
                          expected):
    fork_data = ForkData(
        pre_fork_version=pre_fork_version,
        post_fork_version=post_fork_version,
        fork_slot=fork_slot,
    )
    assert expected == get_fork_version(
        fork_data,
        current_slot,
    )


@pytest.mark.parametrize(
    (
        'pre_fork_version,'
        'post_fork_version,'
        'fork_slot,'
        'current_slot,'
        'domain_type,'
        'expected'
    ),
    [
        (1, 2, 20, 10, 10, 1 * 2 ** 32 + 10),
        (1, 2, 20, 20, 11, 2 * 2 ** 32 + 11),
        (1, 2, 10, 20, 12, 2 * 2 ** 32 + 12),
    ]
)
def test_get_domain(pre_fork_version,
                    post_fork_version,
                    fork_slot,
                    current_slot,
                    domain_type,
                    expected):
    fork_data = ForkData(
        pre_fork_version=pre_fork_version,
        post_fork_version=post_fork_version,
        fork_slot=fork_slot,
    )
    assert expected == get_domain(
        fork_data=fork_data,
        slot=current_slot,
        domain_type=domain_type,
    )


def test_is_double_vote(sample_attestation_data_params):
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

    assert is_double_vote(attestation_data_1, attestation_data_2)

    attestation_data_3_params = {
        **sample_attestation_data_params,
        'slot': 54321,
    }
    attestation_data_3 = AttestationData(**attestation_data_3_params)

    assert not is_double_vote(attestation_data_1, attestation_data_3)


@pytest.mark.parametrize(
    (
        'attestation_1_slot,'
        'attestation_1_justified_slot,'
        'attestation_2_slot,'
        'attestation_2_justified_slot,'
        'expected'
    ),
    [
        (0, 0, 0, 0, False),
        (4, 3, 3, 2, False),  # not (attestation_1_justified_slot < attestation_2_justified_slot
        (4, 0, 3, 1, False),  # not (attestation_2_justified_slot + 1 == attestation_2_slot)
        (4, 0, 4, 3, False),  # not (attestation_2_slot < attestation_1_slot)
        (4, 0, 3, 2, True),
    ],
)
def test_is_surround_vote(sample_attestation_data_params,
                          attestation_1_slot,
                          attestation_1_justified_slot,
                          attestation_2_slot,
                          attestation_2_justified_slot,
                          expected):
    attestation_data_1_params = {
        **sample_attestation_data_params,
        'slot': attestation_1_slot,
        'justified_slot': attestation_1_justified_slot,
    }
    attestation_data_1 = AttestationData(**attestation_data_1_params)

    attestation_data_2_params = {
        **sample_attestation_data_params,
        'slot': attestation_2_slot,
        'justified_slot': attestation_2_justified_slot,
    }
    attestation_data_2 = AttestationData(**attestation_data_2_params)

    assert is_surround_vote(attestation_data_1, attestation_data_2) == expected
