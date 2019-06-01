from typing import Dict, Iterable, Optional, Sequence, Tuple, Type, Union

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    curry,
)

from eth2.beacon.helpers import (
    get_active_validator_indices,
    slot_to_epoch,
)
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Slot,
    ValidatorIndex,
)
from eth2.configs import Eth2Config


# TODO(ralexstokes) integrate `AttestationPool` once it has been merged
class AttestationPool:
    def get_latest_attestation_by_index(index: ValidatorIndex) -> AttestationData:
        return AttestationData(
            slot=1,
            beacon_block_root=0xdeadbeefcafe,
            source_epoch=0,
            source_root=0xdeadbeefcafe,
            target_root=0xdeadbeefcafe,
            shard=1,
            previous_crosslink=0xdeadbeeefcafe,
            crosslink_data_root=0xdeadbeefcafe,
        )


AttestationIndex = Dict[ValidatorIndex, AttestationData]


class Store:
    """
    A private class meant to encapsulate data access for the functionality in this module.
    """
    def __init__(self, db: BeaconChainDB, state: BeaconState, attestation_pool: AttestationPool):
        self.db = db
        self._attestation_index = self._build_attestation_index(state, attestation_pool)

    def _build_attestation_index(self,
                                 state: BeaconState,
                                 attestation_pool: AttestationPool) -> AttestationIndex:
        """
        Assembles a dictionary of latest attestations keyed by validator index.
        Any attestation made by a validator in the ``attestation_pool`` that occur after the last known attestation according to the state take precedence.
        """
        previous_epoch_index = self._mk_pre_index_from_attestations(
            state,
            state.previous_epoch_attestations
        )

        current_epoch_index = self._mk_pre_index_from_attestations(
            state,
            state.current_epoch_attestations
        )

        pool_index = self._mk_pre_index_from_attestations(
            state,
            tuple(attestation for _, attestation in attestation_pool)
        )

        all_attestations_by_index = concat(
            (
                previous_epoch_index,
                current_epoch_index,
                pool_index,
            )
        )
        return valmap(
            second,
            merge_with(
                _take_latest_attestation_by_slot,
                all_attestations_by_index,
            )
        )

    def _get_latest_attestation(self, index: ValidatorIndex) -> Optional[AttestationData]:
        """
        Return the latest attesation we know from the validator with the
        given ``index``.
        """
        return self._attestation_index.get(index, None)

    def _get_block_by_root(self, root: Hash32) -> BaseBeaconBlock:
        return self._db.get_block_by_root(root, self._block_class)

    def get_latest_attestation_target(self, index: ValidatorIndex) -> Optional[BaseBeaconBlock]:
        attestation = self._get_latest_attestation(index)
        if not attestation:
            return None
        target_block = self._get_block_by_root(attestation.beacon_block_root)
        return target_block

    def get_ancestor(self, index):
        """
        Return the block in the chain that is a
        predecessor of ``block`` at the requested ``slot``.
        """
        pass


AttestationTarget = Tuple[ValidatorIndex, Optional[BaseBeaconBlock]]


@curry
def _find_latest_attestation_target(
        store: Store,
        index: ValidatorIndex) -> AttestationTarget:
    return (
        index,
        store.get_latest_attestation_target(index),
    )


@to_tuple
def _find_latest_attestation_targets(state: BeaconState,
                                     store: Store,
                                     config: Eth2Config) -> Iterable[AttestationTarget]:
    epoch = slot_to_epoch(state.slot, config.SLOTS_PER_EPOCH)
    active_validators = get_active_validator_indices(
        state.validator_registry,
        epoch,
    )
    return filter(
        second,
        map(
            _find_latest_attestation_target(store),
            active_validators,
        )
    )


def _get_ancestor(store: Store, block: BaseBeaconBlock, slot: Slot) -> BaseBeaconBlock:
    return store.get_ancestor(block, slot)


def score_block_by_attestations(state: BeaconState,
                                store: Store,
                                attestation_targets: Sequence[AttestationTarget],
                                block: BaseBeaconBlock) -> int:
    """
    Return the total balance attesting to ``block`` based on the ``attestation_targets``.
    """
    return sum(
        state.validator_registry[validator_index].high_balance
        for validator_index, target in attestation_targets
        if _get_ancestor(store, target, block.slot) == block
    )


def score_block_by_root(block: BaseBeaconBlock) -> int:
    return int.from_bytes(block.root, byteorder='big')


@curry
def lmd_ghost_scoring(chain_db: BeaconChainDB,
                      attestation_pool: AttestationPool,
                      state: BeaconState,
                      config: Eth2Config,
                      block: BaseBeaconBlock) -> int:
    """
    Return the score of the ``target_block`` according to the LMD GHOST algorithm,
    using the lexicographic ordering of the block root to break ties.
    """
    store = Store(chain_db, state, attestation_pool)

    attestation_targets = _find_latest_attestation_targets(state, store, config)

    attestation_score = score_block_by_attestations(
        state,
        store,
        attestation_targets,
        block,
    )

    block_root_score = score_block_by_root(block)

    return attestation_score + block_root_score
