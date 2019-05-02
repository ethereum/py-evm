from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
)

import ssz
from ssz.sedes import (
    List,
    Vector,
    bytes32,
    uint64,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.helpers import (
    slot_to_epoch,
    get_temporary_block_header,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    Slot,
    Timestamp,
    ValidatorIndex,
)

from .blocks import BeaconBlockHeader, BeaconBlock
from .eth1_data import Eth1Data
from .eth1_data_vote import Eth1DataVote
from .crosslinks import Crosslink
from .forks import Fork
from .pending_attestations import PendingAttestation
from .validators import Validator


class BeaconState(ssz.Serializable):

    fields = [
        # Misc
        ('slot', uint64),
        ('genesis_time', uint64),
        ('fork', Fork),  # For versioning hard forks

        # Validator registry
        ('validator_registry', List(Validator)),
        ('validator_balances', List(uint64)),
        ('validator_registry_update_epoch', uint64),

        # Randomness and committees
        ('latest_randao_mixes', Vector(bytes32, 1)),
        ('previous_shuffling_start_shard', uint64),
        ('current_shuffling_start_shard', uint64),
        ('previous_shuffling_epoch', uint64),
        ('current_shuffling_epoch', uint64),
        ('previous_shuffling_seed', bytes32),
        ('current_shuffling_seed', bytes32),

        # Finality
        ('previous_epoch_attestations', List(PendingAttestation)),
        ('current_epoch_attestations', List(PendingAttestation)),
        ('previous_justified_epoch', uint64),
        ('current_justified_epoch', uint64),
        ('previous_justified_root', bytes32),
        ('current_justified_root', bytes32),
        # Note: justification_bitfield is meant to be defined as an integer type,
        # so its bit operation is in Python and is easier to specify and implement.
        ('justification_bitfield', uint64),
        ('finalized_epoch', uint64),
        ('finalized_root', bytes32),

        # Recent state
        ('latest_crosslinks', Vector(Crosslink, 1)),
        ('latest_block_roots', Vector(bytes32, 1)),  # Needed to process attestations, older to newer  # noqa: E501
        ('latest_state_roots', Vector(bytes32, 1)),
        ('latest_active_index_roots', Vector(bytes32, 1)),
        ('latest_slashed_balances', Vector(uint64, 1)),  # Balances slashed at every withdrawal period  # noqa: E501
        ('latest_block_header', BeaconBlockHeader),
        ('historical_roots', List(bytes32)),  # allow for a log-sized Merkle proof from any block to any historical block root"  # noqa: E501

        # Ethereum 1.0 chain
        ('latest_eth1_data', Eth1Data),
        ('eth1_data_votes', List(Eth1DataVote)),
        ('deposit_index', uint64),
    ]

    def __init__(
            self,
            *,
            # Misc
            slot: Slot,
            genesis_time: Timestamp,
            fork: Fork,
            # Validator registry
            validator_registry: Sequence[Validator],
            validator_balances: Sequence[Gwei],
            validator_registry_update_epoch: Epoch,
            # Randomness and committees
            latest_randao_mixes: Sequence[Hash32],
            previous_shuffling_start_shard: Shard,
            current_shuffling_start_shard: Shard,
            previous_shuffling_epoch: Epoch,
            current_shuffling_epoch: Epoch,
            previous_shuffling_seed: Hash32,
            current_shuffling_seed: Hash32,
            # Finality
            previous_epoch_attestations: Sequence[PendingAttestation],
            current_epoch_attestations: Sequence[PendingAttestation],
            previous_justified_epoch: Epoch,
            current_justified_epoch: Epoch,
            previous_justified_root: Hash32,
            current_justified_root: Hash32,
            justification_bitfield: int,
            finalized_epoch: Epoch,
            finalized_root: Hash32,
            # Recent state
            latest_crosslinks: Sequence[Crosslink],
            latest_block_roots: Sequence[Hash32],
            latest_state_roots: Sequence[Hash32],
            latest_active_index_roots: Sequence[Hash32],
            latest_slashed_balances: Sequence[Gwei],
            latest_block_header: BeaconBlockHeader,
            historical_roots: Sequence[Hash32],
            # Ethereum 1.0 chain
            latest_eth1_data: Eth1Data,
            eth1_data_votes: Sequence[Eth1DataVote],
            deposit_index: int) -> None:
        if len(validator_registry) != len(validator_balances):
            raise ValueError(
                "The length of validator_registry and validator_balances should be the same."
            )

        super().__init__(
            # Misc
            slot=slot,
            genesis_time=genesis_time,
            fork=fork,
            # Validator registry
            validator_registry=validator_registry,
            validator_balances=validator_balances,
            validator_registry_update_epoch=validator_registry_update_epoch,
            # Randomness and committees
            latest_randao_mixes=latest_randao_mixes,
            previous_shuffling_start_shard=previous_shuffling_start_shard,
            current_shuffling_start_shard=current_shuffling_start_shard,
            previous_shuffling_epoch=previous_shuffling_epoch,
            current_shuffling_epoch=current_shuffling_epoch,
            previous_shuffling_seed=previous_shuffling_seed,
            current_shuffling_seed=current_shuffling_seed,
            # Finality
            previous_epoch_attestations=previous_epoch_attestations,
            current_epoch_attestations=current_epoch_attestations,
            previous_justified_epoch=previous_justified_epoch,
            current_justified_epoch=current_justified_epoch,
            previous_justified_root=previous_justified_root,
            current_justified_root=current_justified_root,
            justification_bitfield=justification_bitfield,
            finalized_epoch=finalized_epoch,
            finalized_root=finalized_root,
            # Recent state
            latest_crosslinks=latest_crosslinks,
            latest_block_roots=latest_block_roots,
            latest_state_roots=latest_state_roots,
            latest_active_index_roots=latest_active_index_roots,
            latest_slashed_balances=latest_slashed_balances,
            latest_block_header=latest_block_header,
            historical_roots=historical_roots,
            # Ethereum 1.0 chain
            latest_eth1_data=latest_eth1_data,
            eth1_data_votes=eth1_data_votes,
            deposit_index=deposit_index,
        )

    def __repr__(self) -> str:
        return '<BeaconState #{0}>'.format(
            encode_hex(self.root)[2:10],
        )

    @property
    def num_validators(self) -> int:
        return len(self.validator_registry)

    @property
    def num_crosslinks(self) -> int:
        return len(self.latest_crosslinks)

    @classmethod
    def create_filled_state(cls,
                            *,
                            genesis_epoch: Epoch,
                            genesis_start_shard: Shard,
                            genesis_slot: Slot,
                            shard_count: int,
                            slots_per_historical_root: int,
                            latest_active_index_roots_length: int,
                            latest_randao_mixes_length: int,
                            latest_slashed_exit_length: int,
                            activated_genesis_validators: Sequence[Validator]=(),
                            genesis_balances: Sequence[Gwei]=()) -> 'BeaconState':
        return cls(
            # Misc
            slot=genesis_slot,
            genesis_time=Timestamp(0),
            fork=Fork(
                previous_version=(0).to_bytes(4, 'little'),
                current_version=(0).to_bytes(4, 'little'),
                epoch=genesis_epoch,
            ),

            # Validator registry
            validator_registry=activated_genesis_validators,
            validator_balances=genesis_balances,
            validator_registry_update_epoch=genesis_epoch,

            # Randomness and committees
            latest_randao_mixes=(ZERO_HASH32,) * latest_randao_mixes_length,
            previous_shuffling_start_shard=genesis_start_shard,
            current_shuffling_start_shard=genesis_start_shard,
            previous_shuffling_epoch=genesis_epoch,
            current_shuffling_epoch=genesis_epoch,
            previous_shuffling_seed=ZERO_HASH32,
            current_shuffling_seed=ZERO_HASH32,

            # Finality
            previous_epoch_attestations=(),
            current_epoch_attestations=(),
            previous_justified_epoch=genesis_epoch,
            current_justified_epoch=genesis_epoch,
            previous_justified_root=ZERO_HASH32,
            current_justified_root=ZERO_HASH32,
            justification_bitfield=0,
            finalized_epoch=genesis_epoch,
            finalized_root=ZERO_HASH32,

            # Recent state
            latest_crosslinks=(
                (
                    Crosslink(
                        epoch=genesis_epoch,
                        crosslink_data_root=ZERO_HASH32,
                    ),
                ) * shard_count
            ),
            latest_block_roots=(ZERO_HASH32,) * slots_per_historical_root,
            latest_state_roots=(ZERO_HASH32,) * slots_per_historical_root,
            latest_active_index_roots=(ZERO_HASH32,) * latest_active_index_roots_length,
            latest_slashed_balances=(Gwei(0),) * latest_slashed_exit_length,
            latest_block_header=get_temporary_block_header(
                BeaconBlock.create_empty_block(genesis_slot),
            ),
            historical_roots=(),

            # Ethereum 1.0 chain data
            latest_eth1_data=Eth1Data.create_empty_data(),
            eth1_data_votes=(),
            deposit_index=len(activated_genesis_validators),
        )

    def update_validator_registry(self,
                                  validator_index: ValidatorIndex,
                                  validator: Validator) -> 'BeaconState':
        """
        Replace ``self.validator_registry[validator_index]`` with ``validator``.
        """
        if validator_index >= self.num_validators or validator_index < 0:
            raise IndexError("Incorrect validator index")

        validator_registry = list(self.validator_registry)
        validator_registry[validator_index] = validator

        updated_state = self.copy(
            validator_registry=tuple(validator_registry),
        )
        return updated_state

    def update_validator_balance(self,
                                 validator_index: ValidatorIndex,
                                 balance: Gwei) -> 'BeaconState':
        """
        Update the balance of validator of the given ``validator_index``.
        """
        if validator_index >= self.num_validators or validator_index < 0:
            raise IndexError("Incorrect validator index")

        validator_balances = list(self.validator_balances)
        validator_balances[validator_index] = balance

        updated_state = self.copy(
            validator_balances=tuple(validator_balances),
        )
        return updated_state

    def update_validator(self,
                         validator_index: ValidatorIndex,
                         validator: Validator,
                         balance: Gwei) -> 'BeaconState':
        """
        Update the ``Validator`` and balance of validator of the given ``validator_index``.
        """
        state = self.update_validator_registry(validator_index, validator)
        state = state.update_validator_balance(validator_index, balance)
        return state

    def current_epoch(self, slots_per_epoch: int) -> Epoch:
        return slot_to_epoch(self.slot, slots_per_epoch)

    def previous_epoch(self, slots_per_epoch: int) -> Epoch:
        return Epoch(self.current_epoch(slots_per_epoch) - 1)

    def next_epoch(self, slots_per_epoch: int) -> Epoch:
        return Epoch(self.current_epoch(slots_per_epoch) + 1)
