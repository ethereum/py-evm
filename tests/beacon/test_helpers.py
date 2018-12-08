import pytest

from eth.beacon.enums.validator_status_codes import (
    ValidatorStatusCode,
)
from eth.beacon.types.attestation_records import AttestationRecord
from eth.beacon.types.shard_committees import ShardCommittee
from eth.beacon.types.validator_records import ValidatorRecord
from eth.beacon.helpers import (
    _get_element_from_recent_list,
    get_active_validator_indices,
    get_attestation_indices,
    get_block_hash,
    get_hashes_from_recent_block_hashes,
    get_hashes_to_sign,
    get_new_shuffling,
    get_shards_committees_for_slot,
    get_signed_parent_hashes,
    get_block_committees_info,
)

from tests.beacon.helpers import (
    get_pseudo_chain,
)


def generate_mock_recent_block_hashes(
        genesis_block,
        current_block_number,
        epoch_length):
    chain_length = (current_block_number // epoch_length + 1) * epoch_length
    blocks = get_pseudo_chain(chain_length, genesis_block)
    recent_block_hashes = [
        b'\x00' * 32
        for i
        in range(epoch_length * 2 - current_block_number)
    ] + [block.hash for block in blocks[:current_block_number]]
    return blocks, recent_block_hashes


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
# Get block hashes
#
@pytest.mark.xfail(reason="Need to be fixed")
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
def test_get_block_hash(
        genesis_block,
        current_block_number,
        target_slot,
        success,
        epoch_length):
    epoch_length = epoch_length

    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_number,
        epoch_length,
    )

    if success:
        block_hash = get_block_hash(
            recent_block_hashes,
            current_block_number,
            target_slot,
            epoch_length,
        )
        assert block_hash == blocks[target_slot].hash
    else:
        with pytest.raises(ValueError):
            get_block_hash(
                recent_block_hashes,
                current_block_number,
                target_slot,
                epoch_length,
            )


@pytest.mark.xfail(reason="Need to be fixed")
@pytest.mark.parametrize(
    (
        'epoch_length,current_block_slot_number,from_slot,to_slot'
    ),
    [
        (20, 10, 2, 7),
        (20, 30, 10, 20),
    ],
)
def test_get_hashes_from_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        from_slot,
        to_slot,
        epoch_length):
    _, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        epoch_length,
    )

    result = get_hashes_from_recent_block_hashes(
        recent_block_hashes,
        current_block_slot_number,
        from_slot,
        to_slot,
        epoch_length,
    )
    assert len(result) == to_slot - from_slot + 1


@pytest.mark.xfail(reason="Need to be fixed")
def test_get_hashes_to_sign(genesis_block, epoch_length):
    epoch_length = epoch_length
    current_block_slot_number = 1
    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        epoch_length,
    )

    block = blocks[current_block_slot_number]
    result = get_hashes_to_sign(
        recent_block_hashes,
        block,
        epoch_length,
    )
    assert len(result) == epoch_length
    assert result[-1] == block.hash


@pytest.mark.xfail(reason="Need to be fixed")
def test_get_new_recent_block_hashes(genesis_block,
                                     epoch_length,
                                     sample_attestation_record_params):
    epoch_length = epoch_length
    current_block_slot_number = 15
    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        epoch_length,
    )

    block = blocks[current_block_slot_number]
    oblique_parent_hashes = [b'\x77' * 32]
    attestation = AttestationRecord(**sample_attestation_record_params).copy(
        slot=10,
        oblique_parent_hashes=oblique_parent_hashes,
    )
    result = get_signed_parent_hashes(
        recent_block_hashes,
        block,
        attestation,
        epoch_length,
    )
    assert len(result) == epoch_length
    assert result[-1] == oblique_parent_hashes[-1]


#
# Get shards_committees or indices
#
@pytest.mark.xfail(reason="Need to be fixed")
@pytest.mark.parametrize(
    (
        'num_validators,slot,success'
    ),
    [
        (100, 0, True),
        (100, 63, True),
        (100, 64, False),
    ],
)
def test_get_shard_committee_for_slot(
        genesis_crystallized_state,
        num_validators,
        slot,
        success,
        epoch_length):
    crystallized_state = genesis_crystallized_state

    if success:
        shards_committees_for_slot = get_shards_committees_for_slot(
            crystallized_state,
            slot,
            epoch_length,
        )
        assert len(shards_committees_for_slot) > 0
        assert len(shards_committees_for_slot[0].committee) > 0
    else:
        with pytest.raises(ValueError):
            get_shards_committees_for_slot(
                crystallized_state,
                slot,
                epoch_length,
            )


@pytest.mark.xfail(reason="Need to be fixed")
# @pytest.mark.parametrize(
#     (
#         'num_validators,'
#         'epoch_length,min_committee_size'
#     ),
#     [
#         (1000, 20, 10),
#     ],
# )
def test_get_attestation_indices(genesis_crystallized_state,
                                 sample_attestation_record_params,
                                 epoch_length,
                                 min_committee_size):
    attestation = AttestationRecord(**sample_attestation_record_params)
    attestation = attestation.copy(
        slot=0,
        shard_id=0,
    )

    attestation_indices = get_attestation_indices(
        genesis_crystallized_state,
        attestation,
        epoch_length,
    )
    assert len(attestation_indices) >= min_committee_size


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
@pytest.mark.xfail(reason="Need to be fixed")
@pytest.mark.parametrize(
    (
        'committee,parent_block_number,result_proposer_index_in_committee'
    ),
    [
        ([0, 1, 2, 3], 0, 0),
        ([0, 1, 2, 3], 2, 2),
        ([0, 1, 2, 3], 11, 3),
        ([], 1, ValueError()),
    ],
)
def test_get_block_committees_info(monkeypatch,
                                   genesis_block,
                                   genesis_crystallized_state,
                                   committee,
                                   parent_block_number,
                                   result_proposer_index_in_committee,
                                   epoch_length):
    from eth.beacon import helpers

    def mock_get_shards_committees_for_slot(parent_block,
                                            crystallized_state,
                                            epoch_length):
        return [
            ShardCommittee(shard_id=1, committee=committee),
        ]

    monkeypatch.setattr(
        helpers,
        'get_shards_committees_for_slot',
        mock_get_shards_committees_for_slot
    )

    parent_block = genesis_block
    parent_block = genesis_block.copy(
        slot_number=parent_block_number,
    )

    if isinstance(result_proposer_index_in_committee, Exception):
        with pytest.raises(ValueError):
            get_block_committees_info(
                parent_block,
                genesis_crystallized_state,
                epoch_length,
            )
    else:
        block_committees_info = get_block_committees_info(
            parent_block,
            genesis_crystallized_state,
            epoch_length,
        )
        assert (
            block_committees_info.proposer_index_in_committee ==
            result_proposer_index_in_committee
        )


def test_get_active_validator_indices(sample_validator_record_params):
    # 3 validators are ACTIVE by default.
    validators = [
        ValidatorRecord(
            **sample_validator_record_params,
        )
        for i in range(3)
    ]
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 3

    # Make one validator becomes PENDING_EXIT.
    validators[0] = validators[0].copy(
        status=ValidatorStatusCode.PENDING_EXIT,
    )
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 3

    # Make one validator becomes PENDING_EXIT.
    validators[0] = validators[0].copy(
        status=ValidatorStatusCode.EXITED_WITHOUT_PENALTY,
    )
    active_validator_indices = get_active_validator_indices(validators)
    assert len(active_validator_indices) == 2
