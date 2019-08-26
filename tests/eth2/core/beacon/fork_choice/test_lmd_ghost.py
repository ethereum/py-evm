import random

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
import pytest

from eth2._utils import bitfield
from eth2.beacon.attestation_helpers import get_attestation_data_slot
from eth2.beacon.committee_helpers import (
    get_committee_count,
    get_crosslink_committee,
    get_start_shard,
)
from eth2.beacon.epoch_processing_helpers import get_attesting_indices
from eth2.beacon.fork_choice.lmd_ghost import (
    Store,
    _balance_for_validator,
    lmd_ghost_scoring,
    score_block_by_root,
)
from eth2.beacon.helpers import (
    compute_epoch_of_slot,
    compute_start_slot_of_epoch,
    get_active_validator_indices,
)
from eth2.beacon.tools.builder.validator import get_crosslink_committees_at_slot
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.typing import Shard
from eth2.configs import CommitteeConfig


# TODO(ralexstokes) merge this and next into tools/builder
@to_dict
def _mk_attestation_inputs_in_epoch(epoch, state, config):
    active_validators_indices = get_active_validator_indices(state.validators, epoch)
    epoch_committee_count = get_committee_count(
        len(active_validators_indices),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )
    epoch_start_shard = get_start_shard(state, epoch, CommitteeConfig(config))
    for shard_offset in random.sample(
        range(epoch_committee_count), epoch_committee_count
    ):
        shard = Shard((epoch_start_shard + shard_offset) % config.SHARD_COUNT)
        committee = get_crosslink_committee(
            state, epoch, shard, CommitteeConfig(config)
        )

        if not committee:
            # empty crosslink committee this epoch
            continue

        attestation_data = AttestationData(
            target=Checkpoint(epoch=epoch), crosslink=Crosslink(shard=shard)
        )
        committee_count = len(committee)
        aggregation_bits = bitfield.get_empty_bitfield(committee_count)
        for index in range(committee_count):
            aggregation_bits = bitfield.set_voted(aggregation_bits, index)

            for index in committee:
                yield (
                    index,
                    (
                        get_attestation_data_slot(state, attestation_data, config),
                        (aggregation_bits, attestation_data),
                    ),
                )


def _mk_attestations_for_epoch_by_count(
    number_of_committee_samples, epoch, state, config
):
    results = {}
    for _ in range(number_of_committee_samples):
        sample = _mk_attestation_inputs_in_epoch(epoch, state, config)
        results = merge(results, sample)
    return results


def _extract_attestations_from_index_keying(values):
    results = ()
    for value in values:
        aggregation_bits, data = second(value)
        attestation = Attestation(aggregation_bits=aggregation_bits, data=data)
        if attestation not in results:
            results += (attestation,)
    return results


def _keep_by_latest_slot(values):
    """
    we get a sequence of (Slot, (Bitfield, AttestationData))
    and return the AttestationData with the highest slot
    """
    return max(values, key=first)[1][1]


def _find_collision(state, config, index, epoch):
    """
    Given a target epoch, make the attestation expected for the
    validator w/ the given index.
    """
    active_validators = get_active_validator_indices(state.validators, epoch)
    committees_per_slot = (
        get_committee_count(
            len(active_validators),
            config.SHARD_COUNT,
            config.SLOTS_PER_EPOCH,
            config.TARGET_COMMITTEE_SIZE,
        )
        // config.SLOTS_PER_EPOCH
    )
    epoch_start_slot = compute_start_slot_of_epoch(epoch, config.SLOTS_PER_EPOCH)
    epoch_start_shard = get_start_shard(state, epoch, CommitteeConfig(config))

    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        offset = committees_per_slot * (slot % config.SLOTS_PER_EPOCH)
        slot_start_shard = (epoch_start_shard + offset) % config.SHARD_COUNT
        for i in range(committees_per_slot):
            shard = Shard((slot_start_shard + i) % config.SHARD_COUNT)
            committee = get_crosslink_committee(
                state, epoch, shard, CommitteeConfig(config)
            )
            if index in committee:
                # TODO(ralexstokes) refactor w/ tools/builder
                attestation_data = AttestationData(
                    target=Checkpoint(epoch=epoch), crosslink=Crosslink(shard=shard)
                )
                committee_count = len(committee)
                aggregation_bits = bitfield.get_empty_bitfield(committee_count)
                for i in range(committee_count):
                    aggregation_bits = bitfield.set_voted(aggregation_bits, i)

                return {
                    index: (slot, (aggregation_bits, attestation_data))
                    for index in committee
                }
    else:
        raise Exception("should have found a duplicate validator")


def _introduce_collisions(all_attestations_by_index, state, config):
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
        src_epoch = compute_epoch_of_slot(src_slot, config.SLOTS_PER_EPOCH)
        dst_epoch = src_epoch + 1

        collision = _find_collision(state, config, index=src_index, epoch=dst_epoch)
        collisions += (merge(dst, collision),)
    return collisions


def _get_committee_count(state, epoch, config):
    active_validators = get_active_validator_indices(state.validators, epoch)
    return get_committee_count(
        len(active_validators),
        config.SHARD_COUNT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )


@pytest.mark.parametrize(
    ("validator_count",),
    [
        (8,),  # low number of validators
        (128,),  # medium number of validators
        # NOTE: the test at 1024 count takes too long :(
        (256,),  # high number of validators
    ],
)
@pytest.mark.parametrize(("collisions_from_another_epoch",), [(True,), (False,)])
def test_store_get_latest_attestation(
    genesis_state, empty_attestation_pool, config, collisions_from_another_epoch
):
    """
    Given some attestations across the various sources, can we
    find the latest ones for each validator?
    """
    some_epoch = 3
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH)
    )
    previous_epoch = state.previous_epoch(config.SLOTS_PER_EPOCH, config.GENESIS_EPOCH)
    previous_epoch_committee_count = _get_committee_count(state, previous_epoch, config)

    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    current_epoch_committee_count = _get_committee_count(state, current_epoch, config)

    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    next_epoch_committee_count = _get_committee_count(state, next_epoch, config)

    number_of_committee_samples = 4
    assert number_of_committee_samples <= previous_epoch_committee_count
    assert number_of_committee_samples <= current_epoch_committee_count
    assert number_of_committee_samples <= next_epoch_committee_count

    # prepare samples from previous epoch
    previous_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples, previous_epoch, state, config
    )
    previous_epoch_attestations = _extract_attestations_from_index_keying(
        previous_epoch_attestations_by_index.values()
    )

    # prepare samples from current epoch
    current_epoch_attestations_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples, current_epoch, state, config
    )
    current_epoch_attestations_by_index = keyfilter(
        lambda index: index not in previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
    )
    current_epoch_attestations = _extract_attestations_from_index_keying(
        current_epoch_attestations_by_index.values()
    )

    # prepare samples for pool, taking half from the current epoch and half from the next epoch
    pool_attestations_in_current_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2, current_epoch, state, config
    )
    pool_attestations_in_next_epoch_by_index = _mk_attestations_for_epoch_by_count(
        number_of_committee_samples // 2, next_epoch, state, config
    )
    pool_attestations_by_index = merge(
        pool_attestations_in_current_epoch_by_index,
        pool_attestations_in_next_epoch_by_index,
    )
    pool_attestations_by_index = keyfilter(
        lambda index: (
            index not in previous_epoch_attestations_by_index
            or index not in current_epoch_attestations_by_index
        ),
        pool_attestations_by_index,
    )
    pool_attestations = _extract_attestations_from_index_keying(
        pool_attestations_by_index.values()
    )

    all_attestations_by_index = (
        previous_epoch_attestations_by_index,
        current_epoch_attestations_by_index,
        pool_attestations_by_index,
    )

    if collisions_from_another_epoch:
        (
            previous_epoch_attestations_by_index,
            current_epoch_attestations_by_index,
            pool_attestations_by_index,
        ) = _introduce_collisions(all_attestations_by_index, state, config)

        previous_epoch_attestations = _extract_attestations_from_index_keying(
            previous_epoch_attestations_by_index.values()
        )
        current_epoch_attestations = _extract_attestations_from_index_keying(
            current_epoch_attestations_by_index.values()
        )
        pool_attestations = _extract_attestations_from_index_keying(
            pool_attestations_by_index.values()
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

    for validator_index in range(len(state.validators)):
        expected_attestation_data = expected_index.get(validator_index, None)
        stored_attestation_data = store._get_latest_attestation(validator_index)
        assert expected_attestation_data == stored_attestation_data


def _mk_block(block_params, slot, parent, block_offset):
    return BeaconBlock(**block_params).copy(
        slot=slot,
        parent_root=parent.signing_root,
        # mix in something unique
        state_root=block_offset.to_bytes(32, byteorder="big"),
    )


def _build_block_tree(
    block_params, root_block, base_slot, forking_descriptor, forking_asymmetry, config
):
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
                block = _mk_block(block_params, slot, parent, block_offset)
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


def _get_committees(state, target_slot, config, sampling_fraction):
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state, target_slot, config=config
    )
    return tuple(
        random.sample(
            crosslink_committees_at_slot,
            int((sampling_fraction * len(crosslink_committees_at_slot))),
        )
    )


def _attach_committee_to_block(block, committee):
    block._committee_data = committee


def _get_committee_from_block(block):
    return getattr(block, "_committee_data", None)


def _attach_attestation_to_block(block, attestation):
    block._attestation = attestation


def _get_attestation_from_block(block):
    return getattr(block, "_attestation", None)


def _attach_committees_to_block_tree(
    state, block_tree, committees_by_slot, config, forking_asymmetry
):
    for level, committees in zip(
        _iter_block_tree_by_slot(block_tree), committees_by_slot
    ):
        block_count = len(level)
        partitions = partition(block_count, committees)
        for block, committee in zip(_iter_block_level_by_block(level), partitions):
            if forking_asymmetry:
                if random.choice([True, False]):
                    # random drop out
                    continue
            _attach_committee_to_block(block, first(committee))


# TODO(ralexstokes) merge in w/ tools/builder
def _mk_attestation_for_block_with_committee(block, committee, shard, config):
    committee_count = len(committee)
    aggregation_bits = bitfield.get_empty_bitfield(committee_count)
    for index in range(committee_count):
        aggregation_bits = bitfield.set_voted(aggregation_bits, index)

    attestation = Attestation(
        aggregation_bits=aggregation_bits,
        data=AttestationData(
            beacon_block_root=block.signing_root,
            target=Checkpoint(
                epoch=compute_epoch_of_slot(block.slot, config.SLOTS_PER_EPOCH)
            ),
            crosslink=Crosslink(shard=shard),
        ),
    )
    return attestation


def _attach_attestations_to_block_tree_with_committees(block_tree, config):
    for block in _iter_block_tree_by_block(block_tree):
        committee_data = _get_committee_from_block(block)
        if not committee_data:
            # w/ asymmetry in forking we may need to skip this step
            continue
        committee, shard = committee_data
        attestation = _mk_attestation_for_block_with_committee(
            block, committee, shard, config
        )
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
    for index in get_attesting_indices(
        state, attestation.data, attestation.aggregation_bits, config
    ):
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
            block.signing_root: block for block in _iter_block_tree_by_block(block_tree)
        }
        self._block_index[root_block.signing_root] = root_block
        self._blocks_by_parent_root = {
            block.parent_root: self._block_index[block.parent_root]
            for block in _iter_block_tree_by_block(block_tree)
        }

    def _find_attestation_targets(self):
        result = {}
        for _, attestation in self._attestation_pool:
            target_slot = get_attestation_data_slot(
                self._state, attestation.data, self._config
            )
            for validator_index in _iter_attestation_by_validator_index(
                self._state, attestation, self._config
            ):
                if validator_index in result:
                    existing = result[validator_index]
                    existing_slot = get_attestation_data_slot(
                        self._state, existing.data, self._config
                    )
                    if existing_slot > target_slot:
                        continue
                result[validator_index] = attestation
        return result

    def _get_attestation_targets(self):
        for index, target in self._latest_attestations.items():
            yield (index, self._block_index[target.data.beacon_block_root])

    def _get_parent_block(self, block):
        return self._blocks_by_parent_root[block.parent_root]

    def _get_ancestor(self, block, slot):
        if block.slot == slot:
            return block
        elif block.slot < slot:
            return None
        else:
            return self._get_ancestor(self._get_parent_block(block), slot)


@pytest.mark.parametrize(
    ("validator_count",),
    [
        (8,),  # low number of validators
        (128,),  # medium number of validators
        (1024,),  # high number of validators
    ],
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
    ],
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
    ],
)
def test_lmd_ghost_fork_choice_scoring(
    sample_beacon_block_params,
    chaindb_at_genesis,
    # see note below on how this is used
    fork_choice_scoring,
    forking_descriptor,
    forking_asymmetry,
    genesis_state,
    empty_attestation_pool,
    config,
):
    """
    Given some blocks and some attestations, can we score them correctly?
    """
    chain_db = chaindb_at_genesis
    root_block = chain_db.get_canonical_head(BeaconBlock)

    some_epoch = 3
    some_slot_offset = 10

    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH)
        + some_slot_offset,
        current_justified_checkpoint=Checkpoint(
            epoch=some_epoch, root=root_block.signing_root
        ),
    )
    assert some_epoch >= state.current_justified_checkpoint.epoch

    # NOTE: the attestations have to be aligned to the blocks which start from ``base_slot``.
    base_slot = compute_start_slot_of_epoch(some_epoch, config.SLOTS_PER_EPOCH) + 1
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
            state, base_slot + slot_offset, config, committee_sampling_fraction
        )
        for slot_offset in range(slot_count)
    )

    _attach_committees_to_block_tree(
        state, block_tree, committees_by_slot, config, forking_asymmetry
    )

    _attach_attestations_to_block_tree_with_committees(block_tree, config)

    attestations = tuple(
        _get_attestation_from_block(block)
        for block in _iter_block_tree_by_block(block_tree)
        if _get_attestation_from_block(block)
    )

    attestation_pool = empty_attestation_pool
    for attestation in attestations:
        attestation_pool.add(attestation)

    store = _store(state, root_block, block_tree, attestation_pool, config)

    score_index = _build_score_index_from_decorated_block_tree(
        block_tree, store, state, config
    )

    for block in _iter_block_tree_by_block(block_tree):
        # NOTE: we use the ``fork_choice_scoring`` fixture, it doesn't matter for this test
        chain_db.persist_block(block, BeaconBlock, fork_choice_scoring)

    scoring_fn = lmd_ghost_scoring(
        chain_db, attestation_pool, state, config, BeaconBlock
    )

    for block in _iter_block_tree_by_block(block_tree):
        score = scoring_fn(block)
        expected_score = score_index[block.signing_root]
        assert score == expected_score
