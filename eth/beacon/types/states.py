from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth.rlp.sedes import (
    uint24,
    uint64,
    hash32,
)
from eth.utils.blake import (
    blake,
)

from .attestation_records import AttestationRecord
from .candidate_pow_receipt_root_records import CandidatePoWReceiptRootRecord
from .crosslink_records import CrosslinkRecord
from .shard_and_committees import ShardAndCommittee
from .shard_reassignment_records import ShardReassignmentRecord
from .validator_records import ValidatorRecord


class BeaconState(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Slot of last validator set change
        ('validator_set_change_slot', uint64),
        # List of validators
        ('validators', CountableList(ValidatorRecord)),
        # Most recent crosslink for each shard
        ('crosslinks', CountableList(CrosslinkRecord)),
        # Last cycle-boundary state recalculation
        ('last_state_recalculation_slot', uint64),
        # Last finalized slot
        ('last_finalized_slot', uint64),
        # Last justified slot
        ('last_justified_slot', uint64),
        # Number of consecutive justified slots
        ('justified_streak', uint64),
        # Committee members and their assigned shard, per slot
        ('shard_and_committee_for_slots', CountableList(CountableList(ShardAndCommittee))),
        # Persistent shard committees
        ('persistent_committees', CountableList(CountableList(uint24))),
        ('persistent_committee_reassignments', CountableList(ShardReassignmentRecord)),
        # Randao seed used for next shuffling
        ('next_shuffling_seed', hash32),
        # Total deposits penalized in the given withdrawal period
        ('deposits_penalized_in_period', CountableList(uint64)),
        # Hash chain of validator set changes (for light clients to easily track deltas)
        ('validator_set_delta_hash_chain', hash32),
        # Current sequence number for withdrawals
        ('current_exit_seq', uint64),
        # Genesis time
        ('genesis_time', uint64),
        # PoW receipt root
        ('processed_pow_receipt_root', hash32),
        ('candidate_pow_receipt_roots', CountableList(CandidatePoWReceiptRootRecord)),
        # Parameters relevant to hard forks / versioning.
        # Should be updated only by hard forks.
        ('pre_fork_version', uint64),
        ('post_fork_version', uint64),
        ('fork_slot_number', uint64),
        # Attestations not yet processed
        ('pending_attestations', CountableList(AttestationRecord)),
        # recent beacon block hashes needed to process attestations, older to newer
        ('recent_block_hashes', CountableList(hash32)),
        # RANDAO state
        ('randao_mix', hash32),
    ]

    def __init__(self,
                 validator_set_change_slot: int,
                 last_state_recalculation_slot: int,
                 last_finalized_slot: int,
                 last_justified_slot: int,
                 justified_streak: int,
                 next_shuffling_seed: Hash32,
                 validator_set_delta_hash_chain: Hash32,
                 current_exit_seq: int,
                 genesis_time: int,
                 processed_pow_receipt_root: Hash32,
                 pre_fork_version: int,
                 post_fork_version: int,
                 fork_slot_number: int,
                 randao_mix: Hash32,
                 validators: Sequence[ValidatorRecord]=None,
                 crosslinks: Sequence[CrosslinkRecord]=None,
                 shard_and_committee_for_slots: Sequence[Sequence[ShardAndCommittee]]=None,
                 persistent_committees: Sequence[Sequence[int]]=None,
                 persistent_committee_reassignments: Sequence[ShardReassignmentRecord]=None,
                 deposits_penalized_in_period: Sequence[int]=None,
                 candidate_pow_receipt_roots: Sequence[CandidatePoWReceiptRootRecord]=None,
                 pending_attestations: Sequence[AttestationRecord]=None,
                 recent_block_hashes: Sequence[Hash32]=None
                 ) -> None:
        if validators is None:
            validators = ()
        if crosslinks is None:
            crosslinks = ()
        if shard_and_committee_for_slots is None:
            shard_and_committee_for_slots = ()
        if persistent_committees is None:
            persistent_committees = ()
        if persistent_committee_reassignments is None:
            persistent_committee_reassignments = ()
        if deposits_penalized_in_period is None:
            deposits_penalized_in_period = ()
        if pending_attestations is None:
            pending_attestations = ()
        if recent_block_hashes is None:
            recent_block_hashes = ()

        super().__init__(
            validator_set_change_slot=validator_set_change_slot,
            validators=validators,
            crosslinks=crosslinks,
            last_state_recalculation_slot=last_state_recalculation_slot,
            last_finalized_slot=last_finalized_slot,
            last_justified_slot=last_justified_slot,
            justified_streak=justified_streak,
            shard_and_committee_for_slots=shard_and_committee_for_slots,
            persistent_committees=persistent_committees,
            persistent_committee_reassignments=persistent_committee_reassignments,
            next_shuffling_seed=next_shuffling_seed,
            deposits_penalized_in_period=deposits_penalized_in_period,
            validator_set_delta_hash_chain=validator_set_delta_hash_chain,
            current_exit_seq=current_exit_seq,
            genesis_time=genesis_time,
            processed_pow_receipt_root=processed_pow_receipt_root,
            candidate_pow_receipt_roots=candidate_pow_receipt_roots,
            pre_fork_version=pre_fork_version,
            post_fork_version=post_fork_version,
            fork_slot_number=fork_slot_number,
            pending_attestations=pending_attestations,
            recent_block_hashes=recent_block_hashes,
            randao_mix=randao_mix,
        )

    def __repr__(self) -> str:
        return 'BeaconState #{0}>'.format(
            encode_hex(self.hash)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = blake(rlp.encode(self))
        return self._hash

    @property
    def num_validators(self) -> int:
        return len(self.validators)

    @property
    def num_crosslinks(self) -> int:
        return len(self.crosslinks)
