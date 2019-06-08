import random

import pytest
from eth_utils import to_dict
from eth_utils.toolz import (
    first,
    keyfilter,
    merge,
    merge_with,
    partition,
    second,
    sliding_window,
)

from eth2._utils import bitfield
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
    get_next_epoch_committee_count,
    get_previous_epoch_committee_count,
)
from eth2.beacon.constants import EMPTY_SIGNATURE, ZERO_HASH32
from eth2.beacon.epoch_processing_helpers import get_attesting_indices
from eth2.beacon.fork_choice.lmd_ghost import (
    Store,
    _balance_for_validator,
    _slot_from_attestation_data,
    lmd_ghost_scoring,
    score_block_by_root,
)
from eth2.beacon.helpers import get_epoch_start_slot, slot_to_epoch
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.crosslinks import Crosslink
from eth2.configs import CommitteeConfig


def _mk_range_for_epoch(epoch, slots_per_epoch):
    start = get_epoch_start_slot(epoch, slots_per_epoch)
    return range(start, start + slots_per_epoch)


@to_dict
def _mk_attestations_for_epoch_by_count(number_of_committee_samples,
                                        epoch_range,
                                        state,
                                        config):
    for _ in range(number_of_committee_samples):
        slot = random.choice(epoch_range)
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            committee_config=CommitteeConfig(config),
        )
        committee, shard = random.choice(crosslink_committees_at_slot)
        attestation_data = AttestationData(
            slot=slot,
            beacon_block_root=ZERO_HASH32,
            source_epoch=0,
            source_root=ZERO_HASH32,
            target_root=ZERO_HASH32,
            shard=shard,
            previous_crosslink=Crosslink(
                epoch=0,
                crosslink_data_root=ZERO_HASH32,
            ),
            crosslink_data_root=ZERO_HASH32,
        )
        committee_count = len(committee)
        aggregation_bitfield = bitfield.get_empty_bitfield(committee_count)
        for index in range(committee_count):
            aggregation_bitfield = bitfield.set_voted(aggregation_bitfield, index)

        for index in committee:
            yield (
                index,
                (
                    slot,
                    (
                        aggregation_bitfield,
                        attestation_data,
                    ),
                ),
            )


def _extract_attestations_from_index_keying(values):
    results = ()
    for value in values:
        aggregation_bitfield, data = second(value)
        attestation = Attestation(
            aggregation_bitfield=aggregation_bitfield,
            data=data,
            custody_bitfield=bytes(),
            aggregate_signature=EMPTY_SIGNATURE,
        )
        if attestation not in results:
            results += (attestation,)
    return results


def _keep_by_latest_slot(values):
    """
    we get a sequence of (Slot, (Bitfield, AttestationData))
    and return the AttestationData with the highest slot
    """
    return max(values, key=first)[1][1]


def _find_collision(state, config, index=None, epoch=None):
    """
    Given a target epoch, make the attestation expected for the
    validator w/ the given index.
    """
    assert index is not None
    assert epoch is not None

    epoch_range = _mk_range_for_epoch(epoch, config.SLOTS_PER_EPOCH)

    for slot in epoch_range:
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            committee_config=CommitteeConfig(config),
        )

        for committee, shard in crosslink_committees_at_slot:
            if index in committee:
                attestation_data = AttestationData(
                    slot=slot,
                    beacon_block_root=ZERO_HASH32,
                    source_epoch=0,
                    source_root=ZERO_HASH32,
                    target_root=ZERO_HASH32,
                    shard=shard,
                    previous_crosslink=Crosslink(
                        epoch=0,
                        crosslink_data_root=ZERO_HASH32,
                    ),
                    crosslink_data_root=ZERO_HASH32,
                )
                committee_count = len(committee)
                aggregation_bitfield = bitfield.get_empty_bitfield(committee_count)
                for i in range(committee_count):
                    aggregation_bitfield = bitfield.set_voted(aggregation_bitfield, i)

                return {
                    index: (
                        slot, (aggregation_bitfield, attestation_data)
                    )
                    for index in committee
                }
    else:
        raise Exception("should have found a duplicate validator")


def _introduce_collisions(all_attestations_by_index,
                          state,
                          config):
    """
    Find some attestations for later epochs for the validators
    that are current attesting in each source of attestation.
    """
    collisions = (all_attestations_by_index[0],)
    for src, dst in sliding_window(2, all_attestations_by_index):
        if not src:
            # src can be empty at low validator count
            collisions += (dst,)
            continue
        src_index = random.choice(list(src.keys()))
        src_val = src[src_index]
        src_slot, _ = src_val
        src_epoch = slot_to_epoch(src_slot, config.SLOTS_PER_EPOCH)
        dst_epoch = src_epoch + 1

        collision = _find_collision(state, config, index=src_index, epoch=dst_epoch)
        collisions += (merge(dst, collision),)
    return collisions


@pytest.mark.parametrize(
    (
        "n",
    ),
    [
        (8,),     # low number of validators
        (128,),   # medium number of validators
        (1024,),  # high number of validators
    ]
)
@pytest.mark.parametrize(
    (
        "collisions",
    ),
    [
        (True,),
        (False,),
    ]
)
def test_store_get_latest_attestation(n_validators_state,
                                      empty_attestation_pool,
                                      config,
                                      collisions):
    """
    Given some attestations across the various sources, can we
    find the latest ones for each validator?
    """
    some_epoch = 3
    state = n_validators_state.copy(
        slot=get_epoch_start_slot(some_epoch, config.SLOTS_PER_EPOCH),
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH)
    previous_epoch_range = _mk_range_for_epoch(previous_epoch, config.SLOTS_PER_EPOCH)
    previous_epoch_committee_count = get_previous_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    current_epoch_range = _mk_range_for_epoch(current_epoch, config.SLOTS_PER_EPOCH)
    current_epoch_committee_count = get_current_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    next_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch_range = _mk_range_for_epoch(next_epoch, config.SLOTS_PER_EPOCH)
    next_epoch_committee_count = get_next_epoch_committee_count(
        state,
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    number_of_committee_samples = 4
    assert number_of_committee_samples <= previous_epoch_committee_count
    assert number_of_committee_samples <= current_epoch_committee_count
    assert number_of_committee_samples <= next_epoch_committee_count

    # prepare samples from previous epoch
    previous_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples,
        previous_epoch_range,
        state,
        config,
    )
    previous_epoch_attestations = _extract_attestations_from_index_keying(
        previous_epoch_attestations_by_index.values(),
    )

    # prepare samples from current epoch
    current_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples,
        current_epoch_range,
        state,
        config,
    )
    current_epoch_attestations_by_index = keyfilter(
        lambda index: index not in previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
    )
    current_epoch_attestations = _extract_attestations_from_index_keying(
        current_epoch_attestations_by_index.values(),
    )

    # prepare samples for pool, taking half from the current epoch and half from the next epoch
    pool_attestations_in_current_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2,
        current_epoch_range,
        state,
        config,
    )
    pool_attestations_in_next_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2,
        next_epoch_range,
        state,
        config,
    )
    pool_attestations_by_index = merge(
        pool_attestations_in_current_epoch_by_index,
        pool_attestations_in_next_epoch_by_index,
    )
    pool_attestations_by_index = keyfilter(
        lambda index: (
            index not in previous_epoch_attestations_by_index or
            index not in current_epoch_attestations_by_index
        ),
        pool_attestations_by_index,
    )
    pool_attestations = _extract_attestations_from_index_keying(
        pool_attestations_by_index.values(),
    )

    all_attestations_by_index = (
        previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
        pool_attestations_by_index,
    )

    if collisions:
        (
            previous_epoch_attestations_by_index,
            current_epoch_attestations_by_index,
            pool_attestations_by_index,
        ) = _introduce_collisions(
            all_attestations_by_index,
            state,
            config,
        )

        previous_epoch_attestations = _extract_attestations_from_index_keying(
            previous_epoch_attestations_by_index.values(),
        )
        current_epoch_attestations = _extract_attestations_from_index_keying(
            current_epoch_attestations_by_index.values(),
        )
        pool_attestations = _extract_attestations_from_index_keying(
            pool_attestations_by_index.values(),
        )

    # build expected results
    expected_index = merge_with(
        _keep_by_latest_slot,
        previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
        pool_attestations_by_index,
    )

    # ensure we get the expected results
    state = state.copy(
        previous_epoch_attestations=previous_epoch_attestations,
        current_epoch_attestations=current_epoch_attestations,
    )

    pool = empty_attestation_pool
    for attestation in pool_attestations:
        pool.add(attestation)

    chain_db = None  # not relevant for this test
    store = Store(chain_db, state, pool, BeaconBlock, config)

    # sanity check
    assert expected_index.keys() == store._attestation_index.keys()

    for validator_index in range(len(state.validator_registry)):
        expected_attestation_data = expected_index.get(validator_index, None)
        stored_attestation_data = store._get_latest_attestation(validator_index)
        assert expected_attestation_data == stored_attestation_data


def _mk_block(block_params, slot, parent, block_offset):
    return BeaconBlock(**block_params).copy(
        slot=slot,
        previous_block_root=parent.signing_root,
        # mix in something unique
        state_root=block_offset.to_bytes(32, byteorder="big"),
    )


def _build_block_tree(block_params,
                      root_block,
                      base_slot,
                      forking_descriptor,
                      forking_asymmetry,
                      config):
    """
    build a block tree according to the data in ``forking_descriptor``, starting at
    the block with root ``base_root``.
    """
    tree = [[root_block]]
    for slot_offset, block_count in enumerate(forking_descriptor):
        slot = base_slot + slot_offset
        blocks = []
        for parent in tree[-1]:
            if forking_asymmetry:
                if random.choice([True, False]):
                    continue
            for block_offset in range(block_count):
                block = _mk_block(
                    block_params,
                    slot,
                    parent,
                    block_offset,
                )
            blocks.append(block)
        tree.append(blocks)
    # other code written w/ expectation that root is not in the tree
    tree.pop(0)
    return tree


def _iter_block_tree_by_slot(tree):
    for level in tree:
        yield level


def _iter_block_level_by_block(level):
    for block in level:
        yield block


def _iter_block_tree_by_block(tree):
    for level in _iter_block_tree_by_slot(tree):
        for block in _iter_block_level_by_block(level):
            yield block


def _get_committees(state,
                    target_slot,
                    config,
                    sampling_fraction):
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state,
        target_slot,
        committee_config=CommitteeConfig(config),
    )
    return tuple(
        random.sample(
            crosslink_committees_at_slot,
            int((sampling_fraction * len(crosslink_committees_at_slot)))
        )
    )


def _attach_committee_to_block(block, committee):
    block._committee_data = committee


def _get_committee_from_block(block):
    return getattr(block, '_committee_data', None)


def _attach_attestation_to_block(block, attestation):
    block._attestation = attestation


def _get_attestation_from_block(block):
    return getattr(block, '_attestation', None)


def _attach_committees_to_block_tree(state,
                                     block_tree,
                                     committees_by_slot,
                                     config,
                                     forking_asymmetry):
    for level, committees in zip(
            _iter_block_tree_by_slot(block_tree),
            committees_by_slot,
    ):
        block_count = len(level)
        partitions = partition(block_count, committees)
        for block, committee in zip(
                _iter_block_level_by_block(level),
                partitions,
        ):
            if forking_asymmetry:
                if random.choice([True, False]):
                    # random drop out
                    continue
            _attach_committee_to_block(block, first(committee))


def _mk_attestation_for_block_with_committee(block, committee, shard):
    committee_count = len(committee)
    aggregation_bitfield = bitfield.get_empty_bitfield(committee_count)
    for index in range(committee_count):
        aggregation_bitfield = bitfield.set_voted(aggregation_bitfield, index)

    attestation = Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=AttestationData(
            slot=block.slot,
            beacon_block_root=block.signing_root,
            source_epoch=0,
            source_root=ZERO_HASH32,
            target_root=ZERO_HASH32,
            shard=shard,
            previous_crosslink=Crosslink(
                epoch=0,
                crosslink_data_root=ZERO_HASH32,
            ),
            crosslink_data_root=ZERO_HASH32,
        ),
        custody_bitfield=bytes(),
        aggregate_signature=EMPTY_SIGNATURE,
    )
    return attestation


def _attach_attestations_to_block_tree_with_committees(block_tree):
    for block in _iter_block_tree_by_block(block_tree):
        committee_data = _get_committee_from_block(block)
        if not committee_data:
            # w/ asymmetry in forking we may need to skip this step
            continue
        committee, shard = committee_data
        attestation = _mk_attestation_for_block_with_committee(block, committee, shard)
        _attach_attestation_to_block(block, attestation)


def _score_block(block, store, state, config):
    return sum(
        _balance_for_validator(state, validator_index)
        for validator_index, target in store._get_attestation_targets()
        if store._get_ancestor(target, block.slot) == block
    ) + score_block_by_root(block)


def _build_score_index_from_decorated_block_tree(block_tree, store, state, config):
    return {
        block.signing_root: _score_block(block, store, state, config)
        for block in _iter_block_tree_by_block(block_tree)
    }


def _iter_attestation_by_validator_index(state, attestation, config):
    for index in get_attesting_indices(state, (attestation,), config):
        yield index


class _store:
    """
    Mock Store class.
    """

    def __init__(self, state, root_block, block_tree, attestation_pool, config):
        self._state = state
        self._block_tree = block_tree
        self._attestation_pool = attestation_pool
        self._config = config
        self._latest_attestations = self._find_attestation_targets()
        self._block_index = {
            block.signing_root: block
            for block in _iter_block_tree_by_block(block_tree)
        }
        self._block_index[root_block.signing_root] = root_block
        self._blocks_by_previous_root = {
            block.previous_block_root: self._block_index[block.previous_block_root]
            for block in _iter_block_tree_by_block(block_tree)
        }

    def _find_attestation_targets(self):
        result = {}
        for _, attestation in self._attestation_pool:
            target_slot = _slot_from_attestation_data(attestation.data)
            for validator_index in _iter_attestation_by_validator_index(
                    self._state,
                    attestation,
                    self._config):
                if validator_index in result:
                    existing = result[validator_index]
                    if _slot_from_attestation_data(existing.data) > target_slot:
                        continue
                result[validator_index] = attestation
        return result

    def _get_attestation_targets(self):
        for index, target in self._latest_attestations.items():
            yield (index, self._block_index[target.data.beacon_block_root])

    def _get_previous_block(self, block):
        return self._blocks_by_previous_root[block.previous_block_root]

    def _get_ancestor(self, block, slot):
        if block.slot == slot:
            return block
        elif block.slot < slot:
            return None
        else:
            return self._get_ancestor(self._get_previous_block(block), slot)


@pytest.mark.parametrize(
    (
        "n",
    ),
    [
        (8,),     # low number of validators
        (128,),   # medium number of validators
        (1024,),  # high number of validators
    ]
)
@pytest.mark.parametrize(
    (
        # controls how many children a parent has
        "forking_descriptor",
    ),
    [
        ((1,),),
        ((2,),),
        ((3,),),
        ((1, 1),),
        ((2, 1),),
        ((3, 2),),
        ((1, 4),),
        ((1, 2, 1),),
    ]
)
@pytest.mark.parametrize(
    (
        # controls how children should be allocated to a given parent
        "forking_asymmetry",
    ),
    [
        # Asymmetry means we may deviate from the description in ``forking_descriptor``.
        (True,),
        # No asymmetry means every parent has
        # the number of children prescribed in ``forking_descriptor``.
        # => randomly drop some blocks from receiving attestations
        (False,),
    ]
)
def test_lmd_ghost_fork_choice_scoring(sample_beacon_block_params,
                                       chaindb_at_genesis,
                                       # see note below on how this is used
                                       fork_choice_scoring,
                                       forking_descriptor,
                                       forking_asymmetry,
                                       n_validators_state,
                                       empty_attestation_pool,
                                       config):
    """
    Given some blocks and some attestations, can we score them correctly?
    """
    chain_db = chaindb_at_genesis
    root_block = chain_db.get_canonical_head(BeaconBlock)

    some_epoch = 3
    some_slot_offset = 10

    state = n_validators_state.copy(
        slot=get_epoch_start_slot(some_epoch, config.SLOTS_PER_EPOCH) + some_slot_offset,
        current_justified_epoch=some_epoch,
        current_justified_root=root_block.signing_root,
    )
    assert some_epoch >= state.current_justified_epoch

    # NOTE: the attestations have to be aligned to the blocks which start from ``base_slot``.
    base_slot = get_epoch_start_slot(some_epoch, config.SLOTS_PER_EPOCH) + 1
    block_tree = _build_block_tree(
        sample_beacon_block_params,
        root_block,
        base_slot,
        forking_descriptor,
        forking_asymmetry,
        config,
    )

    slot_count = len(forking_descriptor)
    committee_sampling_fraction = 1
    committees_by_slot = tuple(
        _get_committees(
            state,
            base_slot + slot_offset,
            config,
            committee_sampling_fraction,
        )
        for slot_offset in range(slot_count)
    )

    _attach_committees_to_block_tree(
        state,
        block_tree,
        committees_by_slot,
        config,
        forking_asymmetry,
    )

    _attach_attestations_to_block_tree_with_committees(
        block_tree,
    )

    attestations = tuple(
        _get_attestation_from_block(block) for block in _iter_block_tree_by_block(
            block_tree,
        ) if _get_attestation_from_block(block)
    )

    attestation_pool = empty_attestation_pool
    for attestation in attestations:
        attestation_pool.add(attestation)

    store = _store(state, root_block, block_tree, attestation_pool, config)

    score_index = _build_score_index_from_decorated_block_tree(
        block_tree,
        store,
        state,
        config,
    )

    for block in _iter_block_tree_by_block(block_tree):
        # NOTE: we use the ``fork_choice_scoring`` fixture, it doesn't matter for this test
        chain_db.persist_block(block, BeaconBlock, fork_choice_scoring)

    scoring_fn = lmd_ghost_scoring(chain_db, attestation_pool, state, config, BeaconBlock)

    for block in _iter_block_tree_by_block(block_tree):
        score = scoring_fn(block)
        expected_score = score_index[block.signing_root]
        assert score == expected_score
