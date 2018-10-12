from abc import (
    ABC,
)
import logging
from typing import (
    Iterable,
    Sequence,
    Tuple,
    Type,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    to_tuple,
    ValidationError,
)


from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    BlockNotFound,
)
from eth.utils.blake import blake
from eth.utils import bls
from eth.utils.bitfield import (
    get_bitfield_length,
    get_empty_bitfield,
    has_voted,
    set_voted,
)
from eth.utils.datatypes import (
    Configurable,
)

from eth.beacon.db.chain import BaseBeaconChainDB
from eth.beacon.helpers import (
    get_attestation_indices,
    get_hashes_to_sign,
    get_new_recent_block_hashes,
    get_block_committees_info,
    get_signed_parent_hashes,
)
from eth.beacon.types.active_states import ActiveState
from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.crystallized_states import CrystallizedState
from eth.beacon.state_machines.configs import BeaconConfig  # noqa: F401


class BaseBeaconStateMachine(Configurable, ABC):
    fork = None  # type: str
    chaindb = None  # type: BaseBeaconChainDB
    config = None  # type: BeaconConfig

    block = None  # type: BaseBeaconBlock

    block_class = None  # type: Type[BaseBeaconBlock]
    crystallized_state_class = None  # type: Type[CrystallizedState]
    active_state_class = None  # type: Type[ActiveState]
    attestation_record_class = None  # type: Type[AttestationRecord]

    # TODO: Add abstractmethods


class BeaconStateMachine(BaseBeaconStateMachine):
    """
    The :class:`~eth.beacon.state_machines.base.BeaconStateMachine` class represents
    the Chain rules for a specific protocol definition such as the Serenity network.
    """

    _crytallized_state = None  # type: CrystallizedState
    _active_state = None  # type: ActiveState

    def __init__(self, chaindb: BaseBeaconChainDB, block: BaseBeaconBlock=None) -> None:
        self.chaindb = chaindb
        if self.block is None:
            # Build a child block of current head
            head = self.chaindb.get_canonical_head()
            self.block = self.get_block_class().from_block(block).copy(
                slot_number=head.slot_number + 1,
                parent_hash=head.hash,
            )
        else:
            self.block = self.get_block_class().from_block(block)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('eth.beacon.state_machines.base.BeaconStateMachine.{0}'.format(
            self.__class__.__name__
        ))

    #
    # Block
    #
    @classmethod
    def get_block_class(cls) -> Type[BaseBeaconBlock]:
        """
        Return the :class:`~eth.beacon.types.blocks.BeaconBlock` class that this
        StateMachine uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this StateMachine")
        else:
            return cls.block_class

    @classmethod
    @to_tuple
    def get_prev_blocks(cls,
                        last_block_hash: Hash32,
                        chaindb: BaseBeaconChainDB,
                        max_search_depth: int,
                        min_slot_number: int) -> Iterable[BaseBeaconBlock]:
        """
        Return the previous blocks.

        Slot numbers are not guaranteed to be contiguous since it is possible for there
        to be no block at a given slot.  The search is bounded by two parameters.

        - `max_search_depth` - The maximum number of slots below the slot of the block denoted by
            `last_block_hash` that we should search.
        - `min_slot_number` - The slot number for which we should NOT include any deeper if reached.
        """
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block = chaindb.get_block_by_hash(last_block_hash)

        for _ in range(max_search_depth):
            yield block
            try:
                block = chaindb.get_block_by_hash(block.parent_hash)
            except (IndexError, BlockNotFound):
                break
            # Only include the blocks that are greater than or equal to min_slot_number.
            if block.slot_number < min_slot_number:
                break

    @property
    def parent_block(self) -> BaseBeaconBlock:
        return self.chaindb.get_block_by_hash(
            self.block.parent_hash
        )

    #
    # CrystallizedState
    #
    @property
    def crystallized_state(self) -> CrystallizedState:
        """
        Return the latest CrystallizedState.
        """
        if self._crytallized_state is None:
            self._crytallized_state = self.chaindb.get_crystallized_state_by_root(
                self.parent_block.crystallized_state_root
            )
        return self._crytallized_state

    @classmethod
    def get_crystallized_state_class(cls) -> Type[CrystallizedState]:
        """
        Return the :class:`~eth.beacon.types.crystallized_states.CrystallizedState` class that this
        StateMachine uses for crystallized_state.
        """
        if cls.crystallized_state_class is None:
            raise AttributeError("No `crystallized_state_class` has been set for this StateMachine")
        else:
            return cls.crystallized_state_class

    #
    # ActiveState
    #
    @property
    def active_state(self) -> ActiveState:
        """
        Return latest active state.

        It was backed up per cycle. The latest ActiveState could be reproduced by
        ``backup_active_state`` and recent blocks.
        """
        if self._active_state is None:
            # Reproduce ActiveState
            backup_active_state_root = self.chaindb.get_active_state_root_by_crystallized(
                self.crystallized_state.hash
            )
            backup_active_state = self.chaindb.get_active_state_by_root(backup_active_state_root)
            backup_active_state_slot = self.crystallized_state.last_state_recalc

            if backup_active_state_root == self.parent_block.active_state_root:
                # The backup ActiveState matches current block.
                self._active_state = backup_active_state
            else:
                # Get recent blocks after last ActiveState backup.
                max_search_depth = self.config.CYCLE_LENGTH * 2
                blocks = tuple(
                    reversed(
                        self.get_prev_blocks(
                            last_block_hash=self.parent_block.hash,
                            chaindb=self.chaindb,
                            max_search_depth=max_search_depth,
                            min_slot_number=backup_active_state_slot
                        )
                    )
                )

                self._active_state = self.get_active_state_class(
                ).from_backup_active_state_and_blocks(
                    backup_active_state,
                    blocks,
                )

        return self._active_state

    @classmethod
    def get_active_state_class(cls) -> Type[ActiveState]:
        """
        Return the :class:`~eth.beacon.types.active_states.ActiveState` class that this
        StateMachine uses for active_state.
        """
        if cls.active_state_class is None:
            raise AttributeError("No `active_state_class` has been set for this StateMachine")
        else:
            return cls.active_state_class

    #
    # AttestationRecord
    #
    @classmethod
    def get_attestation_record_class(cls) -> Type[AttestationRecord]:
        """
        Return the :class:`~eth.beacon.types.attestation_records.AttestationRecord` class that this
        StateMachine uses for the current fork version.
        """
        if cls.attestation_record_class is None:
            raise AttributeError("No `attestation_record_class` has been set for this StateMachine")
        else:
            return cls.attestation_record_class

    @classmethod
    def create_signing_message(cls,
                               slot: int,
                               parent_hashes: Iterable[Hash32],
                               shard_id: int,
                               shard_block_hash: Hash32,
                               justified_slot: int) -> bytes:
        # TODO: will be updated to hashed encoded attestation
        return blake(
            slot.to_bytes(8, byteorder='big') +
            b''.join(parent_hashes) +
            shard_id.to_bytes(2, byteorder='big') +
            shard_block_hash +
            justified_slot.to_bytes(8, 'big')
        )

    #
    # Import block API
    #
    def import_block(
            self,
            block: BaseBeaconBlock) -> Tuple[BaseBeaconBlock, CrystallizedState, ActiveState]:
        """
        Import the given block to the chain.
        """
        processing_block = self.get_block_class().from_block(block)
        processing_block, processed_crystallized_state, processed_active_state = self.process_block(
            self.crystallized_state,
            self.active_state,
            processing_block,
            self.chaindb,
            self.config,
        )

        # Validate state roots
        self.validate_state_roots(
            processed_crystallized_state.hash,
            processed_active_state.hash,
            block,
        )

        self.block = processing_block
        self._update_the_states(processed_crystallized_state, processed_active_state)
        # TODO: persist states in BeaconChain if needed

        return self.block, self.crystallized_state, self.active_state

    #
    # Process block APIs
    #
    @classmethod
    def process_block(
            cls,
            crystallized_state: CrystallizedState,
            active_state: ActiveState,
            block: BaseBeaconBlock,
            chaindb: BaseBeaconChainDB,
            config: BeaconConfig) -> Tuple[BaseBeaconBlock, CrystallizedState, ActiveState]:
        """
        Process ``block`` and return the new crystallized state and active state.
        """
        # Process per block state changes (ActiveState)
        processing_active_state = cls.compute_per_block_transtion(
            crystallized_state,
            active_state,
            block,
            chaindb,
            config.CYCLE_LENGTH,
        )

        # Process per cycle state changes (CrystallizedState and ActiveState)
        processed_crystallized_state, processed_active_state = cls.compute_cycle_transitions(
            crystallized_state,
            processing_active_state,
        )

        # Return the copy
        result_block = block.copy()
        return result_block, processed_crystallized_state, processed_active_state

    @classmethod
    def compute_per_block_transtion(cls,
                                    crystallized_state: CrystallizedState,
                                    active_state: ActiveState,
                                    block: BaseBeaconBlock,
                                    chaindb: BaseBeaconChainDB,
                                    cycle_length: int) -> ActiveState:
        """
        Process ``block`` and return the new ActiveState.


        TODO: It doesn't match the latest spec.
        There will be more fields need to be updated in ActiveState.
        """
        parent_block = chaindb.get_block_by_hash(block.parent_hash)
        recent_block_hashes = get_new_recent_block_hashes(
            active_state.recent_block_hashes,
            parent_block.slot_number,
            block.slot_number,
            block.parent_hash
        )

        if parent_block.parent_hash != GENESIS_PARENT_HASH:
            cls.validate_parent_block_proposer(
                crystallized_state,
                block,
                parent_block,
                cycle_length,
            )
        cls.validate_randao_reveal()

        for attestation in block.attestations:
            cls.validate_attestation(
                block,
                parent_block,
                crystallized_state,
                active_state,
                attestation,
                chaindb,
                cycle_length,
            )

        return active_state.copy(
            recent_block_hashes=recent_block_hashes,
            pending_attestations=(
                active_state.pending_attestations + block.attestations
            ),
        )

    @classmethod
    def compute_cycle_transitions(
            cls,
            crystallized_state: CrystallizedState,
            active_state: ActiveState) -> Tuple[CrystallizedState, ActiveState]:
        # TODO: it's a stub
        return crystallized_state, active_state

    #
    #
    # Proposer APIs
    #
    #
    def propose_block(
        self,
        crystallized_state: CrystallizedState,
        active_state: ActiveState,
        block: BaseBeaconBlock,
        shard_id: int,
        shard_block_hash: Hash32,
        chaindb: BaseBeaconBlock,
        config: BeaconConfig,
        private_key: int
    ) -> Tuple[BaseBeaconBlock, CrystallizedState, ActiveState, 'AttestationRecord']:
        """
        Propose the given block.
        """
        block, post_crystallized_state, post_active_state = self.process_block(
            crystallized_state,
            active_state,
            block,
            chaindb,
            config,
        )

        # Set state roots
        block.copy(
            crystallized_state_root=post_crystallized_state.hash,
            active_state_root=post_active_state,
        )

        proposer_attestation = self.attest_proposed_block(
            post_crystallized_state,
            post_active_state,
            block,
            shard_id,
            shard_block_hash,
            chaindb,
            config.CYCLE_LENGTH,
            private_key,
        )
        return block, post_crystallized_state, post_active_state, proposer_attestation

    def _update_the_states(self,
                           crystallized_state: CrystallizedState,
                           active_state: ActiveState) -> None:
        self._crytallized_state = crystallized_state
        self._active_state = active_state

    def attest_proposed_block(self,
                              post_crystallized_state: CrystallizedState,
                              post_active_state: ActiveState,
                              block: BaseBeaconBlock,
                              shard_id: int,
                              shard_block_hash: Hash32,
                              chaindb: BaseBeaconBlock,
                              cycle_length: int,
                              private_key: int) -> 'AttestationRecord':
        """
        Return the initial attestation by the block proposer.

        The proposer broadcasts zir attestation with the proposed block.
        """
        block_committees_info = get_block_committees_info(
            block,
            post_crystallized_state,
            cycle_length,
        )
        # Vote
        attester_bitfield = set_voted(
            get_empty_bitfield(block_committees_info.proposer_committee_size),
            block_committees_info.proposer_index_in_committee,
        )

        # Get justified_slot and justified_block_hash
        justified_slot = post_crystallized_state.last_justified_slot
        justified_block_hash = chaindb.get_canonical_block_by_slot(justified_slot).hash

        # Get signing message and sign it
        parent_hashes = get_hashes_to_sign(
            post_active_state.recent_block_hashes,
            block,
            cycle_length,
        )
        message = self.create_signing_message(
            block.slot_number,
            parent_hashes,
            shard_id,
            shard_block_hash,
            justified_slot,
        )
        sigs = [
            bls.sign(
                message,
                private_key,
            )
        ]
        aggregate_sig = bls.aggregate_sigs(sigs)

        return self.get_attestation_record_class()(
            slot=block.slot_number,
            shard_id=shard_id,
            oblique_parent_hashes=(),
            shard_block_hash=shard_block_hash,
            attester_bitfield=attester_bitfield,
            justified_slot=justified_slot,
            justified_block_hash=justified_block_hash,
            aggregate_sig=aggregate_sig,
        )

    @classmethod
    def aggregate_attestation_record(cls,
                                     crystallized_state: CrystallizedState,
                                     active_state: ActiveState,
                                     block: BaseBeaconBlock,
                                     votes: Iterable[Tuple[int, bytes, int]],
                                     proposer_attestation: 'AttestationRecord',
                                     cycle_length: int) -> 'AttestationRecord':
        """
        Aggregate the votes.

        TODO: Write tests
        """
        # Get signing message
        parent_hashes = get_hashes_to_sign(
            active_state.recent_block_hashes,
            block,
            cycle_length,
        )
        message = cls.create_signing_message(
            block.slot_number,
            parent_hashes,
            proposer_attestation.shard_id,
            block.shard_block_hash,
            crystallized_state.last_justified_slot,
        )
        # Update the bitfield and append the signatures
        bitfield = proposer_attestation.bitfield
        sigs = []
        for (committee_index, sig, public_key) in votes:
            if bls.verify(message, public_key, sig):
                bitfield = set_voted(bitfield, committee_index)
                sigs.append(sig)

        return proposer_attestation.copy(
            bitfield=bitfield,
            sigs=bls.aggregate_sigs(sigs),
        )

    #
    #
    # Validation
    #
    #

    #
    # Parent block proposer validation
    #
    @classmethod
    def validate_parent_block_proposer(cls,
                                       crystallized_state: CrystallizedState,
                                       block: BaseBeaconBlock,
                                       parent_block: BaseBeaconBlock,
                                       cycle_length: int) -> None:
        if block.slot_number == 0:
            return

        block_committees_info = get_block_committees_info(
            parent_block,
            crystallized_state,
            cycle_length,
        )

        if len(block.attestations) == 0:
            raise ValidationError(
                "block.attestations should not be an empty list"
            )
        attestation = block.attestations[0]

        is_proposer_attestation = (
            attestation.shard_id == block_committees_info.proposer_shard_id and
            attestation.slot == parent_block.slot_number and
            has_voted(
                attestation.attester_bitfield,
                block_committees_info.proposer_index_in_committee
            )
        )
        if not is_proposer_attestation:
            raise ValidationError(
                "Proposer of parent block should be one of the attesters in block.attestions[0]:\n"
                "\tExpected: proposer index in committee: %d, shard_id: %d, slot: %d\n"
                "\tFound: shard_id: %d, slot: %d, voted: %s" % (
                    block_committees_info.proposer_index_in_committee,
                    block_committees_info.proposer_shard_id,
                    parent_block.slot_number,
                    attestation.shard_id,
                    attestation.slot,
                    has_voted(
                        attestation.attester_bitfield,
                        block_committees_info.proposer_index_in_committee,
                    ),
                )
            )

    #
    # Randao reveal validation
    #
    @classmethod
    def validate_randao_reveal(cls) -> None:
        # TODO: it's a stub
        return

    #
    # Attestation validation
    #
    @classmethod
    def validate_attestation(cls,
                             block: BaseBeaconBlock,
                             parent_block: BaseBeaconBlock,
                             crystallized_state: CrystallizedState,
                             active_state: ActiveState,
                             attestation: 'AttestationRecord',
                             chaindb: BaseBeaconChainDB,
                             cycle_length: int) -> None:
        """
        Validate the given ``attestation``.

        Raise ``ValidationError`` if it's invalid.
        """
        cls.validate_slot(
            parent_block,
            attestation,
            cycle_length,
        )

        cls.validate_justified(
            crystallized_state,
            attestation,
            chaindb,
        )

        attestation_indices = get_attestation_indices(
            crystallized_state,
            attestation,
            cycle_length,
        )

        cls.validate_bitfield(attestation, attestation_indices)

        cls.validate_version(crystallized_state, attestation)

        parent_hashes = get_signed_parent_hashes(
            active_state.recent_block_hashes,
            block,
            attestation,
            cycle_length,
        )
        cls.validate_aggregate_sig(
            crystallized_state,
            attestation,
            attestation_indices,
            parent_hashes,
        )

    @classmethod
    def validate_slot(cls,
                      parent_block: BaseBeaconBlock,
                      attestation: 'AttestationRecord',
                      cycle_length: int) -> None:
        """
        Validate ``slot`` field.

        Raise ``ValidationError`` if it's invalid.
        """
        if attestation.slot > parent_block.slot_number:
            raise ValidationError(
                "Attestation slot number too high:\n"
                "\tFound: %s Needed less than or equal to %s" %
                (attestation.slot, parent_block.slot_number)
            )
        if attestation.slot < max(parent_block.slot_number - cycle_length + 1, 0):
            raise ValidationError(
                "Attestation slot number too low:\n"
                "\tFound: %s, Needed greater than or equalt to: %s" %
                (
                    attestation.slot,
                    max(parent_block.slot_number - cycle_length + 1, 0)
                )
            )

    @classmethod
    def validate_justified(cls,
                           crystallized_state: CrystallizedState,
                           attestation: 'AttestationRecord',
                           chaindb: BaseBeaconChainDB) -> None:
        """
        Validate ``justified_slot`` and ``justified_block_hash`` fields.

        Raise ``ValidationError`` if it's invalid.
        """
        if attestation.justified_slot > crystallized_state.last_justified_slot:
            raise ValidationError(
                "attestation.justified_slot %s should be equal to or earlier than"
                " crystallized_state.last_justified_slot %s" % (
                    attestation.justified_slot,
                    crystallized_state.last_justified_slot,
                )
            )

        justified_block = chaindb.get_block_by_hash(attestation.justified_block_hash)
        if justified_block is None:
            raise ValidationError(
                "justified_block_hash %s is not in the canonical chain" %
                attestation.justified_block_hash
            )
        if justified_block.slot_number != attestation.justified_slot:
            raise ValidationError(
                "justified_slot %s doesn't match justified_block_hash" % attestation.justified_slot
            )

    @classmethod
    def validate_bitfield(cls,
                          attestation: 'AttestationRecord',
                          attestation_indices: Sequence[int]) -> None:
        """
        Validate ``attester_bitfield`` field.

        Raise ``ValidationError`` if it's invalid.
        """
        if len(attestation.attester_bitfield) != get_bitfield_length(len(attestation_indices)):
            raise ValidationError(
                "Attestation has incorrect bitfield length. Found: %s, Expected: %s" %
                (len(attestation.attester_bitfield), get_bitfield_length(len(attestation_indices)))
            )

        # check if end bits are zero
        last_bit = len(attestation_indices)
        if last_bit % 8 != 0:
            for i in range(8 - last_bit % 8):
                if has_voted(attestation.attester_bitfield, last_bit + i):
                    raise ValidationError("Attestation has non-zero trailing bits")

    @classmethod
    def validate_aggregate_sig(cls,
                               crystallized_state: CrystallizedState,
                               attestation: 'AttestationRecord',
                               attestation_indices: Iterable[int],
                               parent_hashes: Iterable[Hash32]) -> None:
        """
        Validate ``aggregate_sig`` field.

        Raise ``ValidationError`` if it's invalid.
        """
        pub_keys = [
            crystallized_state.validators[validator_index].pubkey
            for committee_index, validator_index in enumerate(attestation_indices)
            if has_voted(attestation.attester_bitfield, committee_index)
        ]

        message = cls.create_signing_message(
            attestation.slot,
            parent_hashes,
            attestation.shard_id,
            attestation.shard_block_hash,
            attestation.justified_slot,
        )
        if not bls.verify(message, bls.aggregate_pubs(pub_keys), attestation.aggregate_sig):
            raise ValidationError("Attestation aggregate signature fails")

    @classmethod
    def validate_version(cls,
                         crystallized_state: CrystallizedState,
                         attestation: 'AttestationRecord') -> None:
        # TODO: it's a stub
        return

    #
    # State roots validation
    #
    @classmethod
    def validate_state_roots(cls,
                             crystallized_state_root: Hash32,
                             active_state_root: Hash32,
                             block: BaseBeaconBlock) -> None:
        """
        Validate block ``crystallized_state_root`` and ``active_state_root`` fields.

        Raise ``ValidationError`` if it's invalid.
        """
        if crystallized_state_root != block.crystallized_state_root:
            raise ValidationError(
                "Crystallized state root incorrect. Found: %s, Expected: %s" %
                (crystallized_state_root, block.crystallized_state_root)
            )
        if active_state_root != block.active_state_root:
            raise ValidationError(
                "Active state root incorrect. Found: %s, Expected: %s" %
                (active_state_root, block.active_state_root)
            )
