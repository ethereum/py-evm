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

from .pending_attestation_records import PendingAttestationRecord
from .candidate_pow_receipt_root_records import CandidatePoWReceiptRootRecord
from .crosslink_records import CrosslinkRecord
from .fork_data import ForkData
from .shard_committees import ShardCommittee
from .shard_reassignment_records import ShardReassignmentRecord
from .validator_records import ValidatorRecord


class BeaconState(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Validator registry
        ('validator_registry', CountableList(ValidatorRecord)),
        ('validator_registry_latest_change_slot', uint64),
        ('validator_registry_exit_count', uint64),
        ('validator_registry_delta_chain_tip', hash32),  # For light clients to easily track delta

        # Randomness and committees
        ('randao_mix', hash32),
        ('next_seed', hash32),
        ('shard_committees_at_slots', CountableList(CountableList((ShardCommittee)))),
        ('persistent_committees', CountableList(CountableList(uint24))),
        ('persistent_committee_reassignments', CountableList(ShardReassignmentRecord)),

        # Finality
        ('previous_justified_slot', uint64),
        ('justified_slot', uint64),
        ('justification_bitfield', uint64),
        ('finalized_slot', uint64),

        # Recent state
        ('latest_crosslinks', CountableList(CrosslinkRecord)),
        ('latest_state_recalculation_slot', uint64),
        ('latest_block_hashes', CountableList(hash32)),  # Needed to process attestations, older to newer  # noqa: E501
        ('latest_penalized_exit_balances', CountableList(uint64)),  # Balances penalized at every withdrawal period  # noqa: E501
        ('latest_attestations', CountableList(PendingAttestationRecord)),

        # PoW receipt root
        ('processed_pow_receipt_root', hash32),
        ('candidate_pow_receipt_roots', CountableList(CandidatePoWReceiptRootRecord)),

        # Misc
        ('genesis_time', uint64),
        ('fork_data', ForkData),  # For versioning hard forks
    ]

    def __init__(
            self,
            validator_registry_latest_change_slot: int,
            validator_registry_exit_count: int,
            validator_registry_delta_chain_tip: Hash32,
            randao_mix: Hash32,
            next_seed: Hash32,
            previous_justified_slot: int,
            justified_slot: int,
            justification_bitfield: int,
            finalized_slot: int,
            processed_pow_receipt_root: Hash32,
            genesis_time: int,
            fork_data: ForkData,
            validator_registry: Sequence[ValidatorRecord]=None,
            shard_committees_at_slots: Sequence[Sequence[ShardCommittee]]=None,
            persistent_committees: Sequence[Sequence[int]]=None,
            persistent_committee_reassignments: Sequence[ShardReassignmentRecord]=None,
            latest_crosslinks: Sequence[CrosslinkRecord]=None,
            latest_state_recalculation_slot: Sequence[int]=None,
            latest_block_hashes: Sequence[Hash32]=None,
            latest_penalized_exit_balances: Sequence[int]=None,
            latest_attestations: Sequence[PendingAttestationRecord]=None,
            candidate_pow_receipt_roots: Sequence[CandidatePoWReceiptRootRecord]=None,
    ) -> None:
        if validator_registry is None:
            validator_registry = ()
        if shard_committees_at_slots is None:
            shard_committees_at_slots = ()
        if persistent_committees is None:
            persistent_committees = ()
        if latest_crosslinks is None:
            latest_crosslinks = ()
        if latest_state_recalculation_slot is None:
            latest_state_recalculation_slot = ()
        if latest_penalized_exit_balances is None:
            latest_penalized_exit_balances = ()
        if latest_penalized_exit_balances is None:
            latest_penalized_exit_balances = ()
        if latest_attestations is None:
            latest_attestations = ()
        if candidate_pow_receipt_roots is None:
            candidate_pow_receipt_roots = ()

        super().__init__(
            validator_registry=validator_registry,
            validator_registry_latest_change_slot=validator_registry_latest_change_slot,
            validator_registry_exit_count=validator_registry_exit_count,
            validator_registry_delta_chain_tip=validator_registry_delta_chain_tip,
            randao_mix=randao_mix,
            next_seed=next_seed,
            shard_committees_at_slots=shard_committees_at_slots,
            persistent_committees=persistent_committees,
            persistent_committee_reassignments=persistent_committee_reassignments,
            previous_justified_slot=previous_justified_slot,
            justified_slot=justified_slot,
            justification_bitfield=justification_bitfield,
            finalized_slot=finalized_slot,
            latest_crosslinks=latest_crosslinks,
            latest_state_recalculation_slot=latest_state_recalculation_slot,
            latest_block_hashes=latest_block_hashes,
            latest_penalized_exit_balances=latest_penalized_exit_balances,
            latest_attestations=latest_attestations,
            processed_pow_receipt_root=processed_pow_receipt_root,
            candidate_pow_receipt_roots=candidate_pow_receipt_roots,
            genesis_time=genesis_time,
            fork_data=fork_data,
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
        return len(self.validator_registry)

    @property
    def num_crosslinks(self) -> int:
        return len(self.latest_crosslinks)
