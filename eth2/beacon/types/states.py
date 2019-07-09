from typing import (
    Any,
    Callable,
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

from eth2._utils.tuple import (
    update_tuple_item,
    update_tuple_item_with_fn,
)
from eth2.configs import Eth2Config
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    Slot,
    Timestamp,
    ValidatorIndex,
)

from .block_headers import (
    BeaconBlockHeader,
    default_beacon_block_header,
)
from .eth1_data import (
    Eth1Data,
    default_eth1_data,
)
from .crosslinks import (
    Crosslink,
    default_crosslink,
)
from .forks import (
    Fork,
    default_fork,
)
from .pending_attestations import PendingAttestation
from .validators import Validator

from .defaults import (
    default_timestamp,
    default_slot,
    default_tuple,
    default_tuple_of_size,
    default_shard,
    default_epoch,
)


class BeaconState(ssz.Serializable):

    fields = [
        # Versioning
        ('genesis_time', uint64),
        ('slot', uint64),
        ('fork', Fork),

        # History
        ('latest_block_header', BeaconBlockHeader),
        ('block_roots', Vector(bytes32, 1)),  # Needed to process attestations, older to newer  # noqa: E501
        ('state_roots', Vector(bytes32, 1)),
        ('historical_roots', List(bytes32)),  # allow for a log-sized Merkle proof from any block to any historical block root  # noqa: E501

        # Ethereum 1.0 chain
        ('eth1_data', Eth1Data),
        ('eth1_data_votes', List(Eth1Data)),
        ('eth1_deposit_index', uint64),

        # Validator registry
        ('validators', List(Validator)),
        ('balances', List(uint64)),

        # Shuffling
        ('start_shard', uint64),
        ('randao_mixes', Vector(bytes32, 1)),
        ('active_index_roots', Vector(bytes32, 1)),

        # Slashings
        ('slashed_balances', Vector(uint64, 1)),  # Balances slashed at every withdrawal period  # noqa: E501

        # Attestations
        ('previous_epoch_attestations', List(PendingAttestation)),
        ('current_epoch_attestations', List(PendingAttestation)),

        # Crosslinks
        ('previous_crosslinks', Vector(Crosslink, 1)),
        ('current_crosslinks', Vector(Crosslink, 1)),

        # Justification
        ('previous_justified_epoch', uint64),
        ('previous_justified_root', bytes32),
        ('current_justified_epoch', uint64),
        ('current_justified_root', bytes32),
        # Note: justification_bitfield is meant to be defined as an integer type,
        # so its bit operation is in Python and is easier to specify and implement.
        ('justification_bitfield', uint64),

        # Finality
        ('finalized_epoch', uint64),
        ('finalized_root', bytes32),
    ]

    def __init__(
            self,
            *,
            genesis_time: Timestamp=default_timestamp,
            slot: Slot=default_slot,
            fork: Fork=default_fork,
            latest_block_header: BeaconBlockHeader=default_beacon_block_header,
            block_roots: Sequence[Hash32]=default_tuple,
            state_roots: Sequence[Hash32]=default_tuple,
            historical_roots: Sequence[Hash32]=default_tuple,
            eth1_data: Eth1Data=default_eth1_data,
            eth1_data_votes: Sequence[Eth1Data]=default_tuple,
            eth1_deposit_index: int=0,
            validators: Sequence[Validator]=default_tuple,
            balances: Sequence[Gwei]=default_tuple,
            start_shard: Shard=default_shard,
            randao_mixes: Sequence[Hash32]=default_tuple,
            active_index_roots: Sequence[Hash32]=default_tuple,
            slashed_balances: Sequence[Gwei]=default_tuple,
            previous_epoch_attestations: Sequence[PendingAttestation]=default_tuple,
            current_epoch_attestations: Sequence[PendingAttestation]=default_tuple,
            previous_crosslinks: Sequence[Crosslink]=default_tuple,
            current_crosslinks: Sequence[Crosslink]=default_tuple,
            previous_justified_epoch: Epoch=default_epoch,
            previous_justified_root: Hash32=ZERO_HASH32,
            current_justified_epoch: Epoch=default_epoch,
            current_justified_root: Hash32=ZERO_HASH32,
            justification_bitfield: int=0,
            finalized_epoch: Epoch=default_epoch,
            finalized_root: Hash32=ZERO_HASH32,
            config: Eth2Config=None) -> None:
        if len(validators) != len(balances):
            raise ValueError(
                "The length of validators and balances lists should be the same."
            )

        if config:
            # try to provide sane defaults
            if block_roots == default_tuple:
                block_roots = default_tuple_of_size(config.SLOTS_PER_HISTORICAL_ROOT, ZERO_HASH32)
            if state_roots == default_tuple:
                state_roots = default_tuple_of_size(config.SLOTS_PER_HISTORICAL_ROOT, ZERO_HASH32)
            if randao_mixes == default_tuple:
                randao_mixes = default_tuple_of_size(
                    config.EPOCHS_PER_HISTORICAL_VECTOR,
                    ZERO_HASH32
                )
            if active_index_roots == default_tuple:
                active_index_roots = default_tuple_of_size(
                    config.EPOCHS_PER_HISTORICAL_VECTOR,
                    ZERO_HASH32
                )
            if slashed_balances == default_tuple:
                slashed_balances = default_tuple_of_size(
                    config.EPOCHS_PER_SLASHED_BALANCES_VECTOR,
                    Gwei(0),
                )
            if previous_crosslinks == default_tuple:
                previous_crosslinks = default_tuple_of_size(
                    config.SHARD_COUNT,
                    default_crosslink,
                )
            if current_crosslinks == default_tuple:
                current_crosslinks = default_tuple_of_size(
                    config.SHARD_COUNT,
                    default_crosslink,
                )

        super().__init__(
            genesis_time=genesis_time,
            slot=slot,
            fork=fork,
            latest_block_header=latest_block_header,
            block_roots=block_roots,
            state_roots=state_roots,
            historical_roots=historical_roots,
            eth1_data=eth1_data,
            eth1_data_votes=eth1_data_votes,
            eth1_deposit_index=eth1_deposit_index,
            validators=validators,
            balances=balances,
            start_shard=start_shard,
            randao_mixes=randao_mixes,
            active_index_roots=active_index_roots,
            slashed_balances=slashed_balances,
            previous_epoch_attestations=previous_epoch_attestations,
            current_epoch_attestations=current_epoch_attestations,
            previous_crosslinks=previous_crosslinks,
            current_crosslinks=current_crosslinks,
            previous_justified_epoch=previous_justified_epoch,
            previous_justified_root=previous_justified_root,
            current_justified_epoch=current_justified_epoch,
            current_justified_root=current_justified_root,
            justification_bitfield=justification_bitfield,
            finalized_epoch=finalized_epoch,
            finalized_root=finalized_root,
        )

    def __repr__(self) -> str:
        return f"<BeaconState #{self.slot} {encode_hex(self.root)[2:10]}>"

    @property
    def validator_count(self) -> int:
        return len(self.validators)

    def update_validator(self,
                         validator_index: ValidatorIndex,
                         validator: Validator,
                         balance: Gwei=None) -> 'BeaconState':
        """
        Replace ``self.validators[validator_index]`` with ``validator``.

        Callers can optionally provide a ``balance`` which will replace
        ``self.balances[validator_index] with ``balance``.
        """
        if (
                validator_index >= len(self.validators) or
                validator_index >= len(self.balances) or
                validator_index < 0
        ):
            raise IndexError("Incorrect validator index")

        state = self.update_validator_with_fn(
            validator_index,
            lambda *_: validator,
        )
        if balance:
            return state._update_validator_balance(
                validator_index,
                balance,
            )
        else:
            return state

    def update_validator_with_fn(self,
                                 validator_index: ValidatorIndex,
                                 fn: Callable[[Validator, Any], Validator],
                                 *args: Any) -> 'BeaconState':
        """
        Replace ``self.validators[validator_index]`` with
        the result of calling ``fn`` on the existing ``validator``.
        Any auxillary args passed in ``args`` are provided to ``fn`` along with the
        ``validator``.
        """
        if validator_index >= len(self.validators) or validator_index < 0:
            raise IndexError("Incorrect validator index")

        return self.copy(
            validators=update_tuple_item_with_fn(
                self.validators,
                validator_index,
                fn,
                *args,
            ),
        )

    def _update_validator_balance(self,
                                  validator_index: ValidatorIndex,
                                  balance: Gwei) -> 'BeaconState':
        """
        Update the balance of validator of the given ``validator_index``.
        """
        if validator_index >= len(self.balances) or validator_index < 0:
            raise IndexError("Incorrect validator index")

        return self.copy(
            balances=update_tuple_item(
                self.balances,
                validator_index,
                balance,
            )
        )

    def current_epoch(self, slots_per_epoch: int) -> Epoch:
        return slot_to_epoch(self.slot, slots_per_epoch)

    def previous_epoch(self, slots_per_epoch: int, genesis_epoch: Epoch) -> Epoch:
        current_epoch = self.current_epoch(slots_per_epoch)
        if current_epoch == genesis_epoch:
            return genesis_epoch
        else:
            return Epoch(current_epoch - 1)

    def next_epoch(self, slots_per_epoch: int) -> Epoch:
        return Epoch(self.current_epoch(slots_per_epoch) + 1)
