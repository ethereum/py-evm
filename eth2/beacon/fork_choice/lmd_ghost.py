from typing import Dict, Iterable, Optional, Sequence, Tuple, Type, Union

from eth_typing import (
    Hash32,
)
from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    curry,
    first,
    mapcat,
    merge,
    merge_with,
    second,
    valmap,
)

from eth2.beacon.attestation_helpers import (
    get_attestation_data_slot,
)
from eth2.beacon.epoch_processing_helpers import (
    get_attesting_indices,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    slot_to_epoch,
)
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.pending_attestations import PendingAttestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Gwei,
    Slot,
    ValidatorIndex,
)
from eth2.configs import Eth2Config, CommitteeConfig


# TODO(ralexstokes) integrate `AttestationPool` once it has been merged
AttestationIndex = Dict[ValidatorIndex, AttestationData]
PreIndex = Dict[ValidatorIndex, Tuple[Slot, AttestationData]]
AttestationLike = Union[Attestation, PendingAttestation]


def _take_latest_attestation_by_slot(
        candidates: Sequence[Tuple[Slot, AttestationData]]) -> Tuple[Slot, AttestationData]:
    return max(candidates, key=first)


class Store:
    """
    A private class meant to encapsulate data access for the functionality in this module.
    """
    def __init__(self,
                 chain_db: BeaconChainDB,
                 state: BeaconState,
                 attestation_pool: AttestationPool,
                 block_class: Type[BaseBeaconBlock],
                 config: Eth2Config):
        self._db = chain_db
        self._block_class = block_class
        self._config = config
        self._attestation_index = self._build_attestation_index(state, attestation_pool)

    @curry
    def _mk_pre_index_from_attestation(self,
                                       state: BeaconState,
                                       attestation: AttestationLike) -> Iterable[PreIndex]:
        attestation_data = attestation.data
        slot = get_attestation_data_slot(state, attestation_data, self._config)

        return (
            {index: (slot, attestation_data)}
            for index in get_attesting_indices(
                state,
                attestation.data,
                attestation.aggregation_bitfield,
                CommitteeConfig(self._config),
            )
        )

    def _mk_pre_index_from_attestations(self,
                                        state: BeaconState,
                                        attestations: Sequence[AttestationLike]) -> PreIndex:
        """
        A 'pre-index' is a Dict[ValidatorIndex, Tuple[Slot, AttestationData]].
        """
        return merge(
            *mapcat(
                self._mk_pre_index_from_attestation(state),
                attestations,
            )
        )

    def _build_attestation_index(self,
                                 state: BeaconState,
                                 attestation_pool: AttestationPool) -> AttestationIndex:
        """
        Assembles a dictionary of latest attestations keyed by validator index.
        Any attestation made by a validator in the ``attestation_pool`` that occur after the
        last known attestation according to the state take precedence.

        We start by building a 'pre-index' from all known attestations which map validator
        indices to a pair of slot and attestation data. A final index is built from all
        pre-indices by keeping the entry with the highest slot across the set of all
        duplicates in the pre-indices keyed by validator index.
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

        index_by_latest_slot = merge_with(
            _take_latest_attestation_by_slot,
            previous_epoch_index,
            current_epoch_index,
            pool_index,
        )
        # convert the index to a mapping of ValidatorIndex -> (latest) Attestation
        return valmap(
            second,
            index_by_latest_slot,
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
        try:
            target_block = self._get_block_by_root(attestation.beacon_block_root)
        except KeyError:
            # attestation made for a block we have not imported
            return None
        return target_block

    def _get_parent_block(self, block: BaseBeaconBlock) -> BaseBeaconBlock:
        return self._db.get_block_by_root(block.parent_root, self._block_class)

    def get_ancestor(self, block: BaseBeaconBlock, slot: Slot) -> BaseBeaconBlock:
        """
        Return the block in the chain that is a
        predecessor of ``block`` at the requested ``slot``.
        """
        if block.slot == slot:
            return block
        elif block.slot < slot:
            return None
        else:
            return self.get_ancestor(self._get_parent_block(block), slot)


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
        state.validators,
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


def _balance_for_validator(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    return state.validators[validator_index].effective_balance


def score_block_by_attestations(state: BeaconState,
                                store: Store,
                                attestation_targets: Sequence[AttestationTarget],
                                block: BaseBeaconBlock) -> int:
    """
    Return the total balance attesting to ``block`` based on the ``attestation_targets``.
    """
    return sum(
        _balance_for_validator(state, validator_index)
        for validator_index, target in attestation_targets
        if _get_ancestor(store, target, block.slot) == block
    )


def score_block_by_root(block: BaseBeaconBlock) -> int:
    return int.from_bytes(block.root[:8], byteorder='big')


@curry
def lmd_ghost_scoring(chain_db: BeaconChainDB,
                      attestation_pool: AttestationPool,
                      state: BeaconState,
                      config: Eth2Config,
                      block_class: Type[BaseBeaconBlock],
                      block: BaseBeaconBlock) -> int:
    """
    Return the score of the ``target_block`` according to the LMD GHOST algorithm,
    using the lexicographic ordering of the block root to break ties.
    """
    store = Store(chain_db, state, attestation_pool, block_class, config)

    attestation_targets = _find_latest_attestation_targets(state, store, config)

    attestation_score = score_block_by_attestations(
        state,
        store,
        attestation_targets,
        block,
    )

    block_root_score = score_block_by_root(block)

    return attestation_score + block_root_score
