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
from eth.beacon._utils.hash import (
    hash_eth2,
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
        # Misc
        ('slot', uint64),
        ('genesis_time', uint64),
        ('fork_data', ForkData),  # For versioning hard forks

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
        ('latest_block_roots', CountableList(hash32)),  # Needed to process attestations, older to newer  # noqa: E501
        ('latest_penalized_exit_balances', CountableList(uint64)),  # Balances penalized at every withdrawal period  # noqa: E501
        ('latest_attestations', CountableList(PendingAttestationRecord)),
        ('batched_block_roots', CountableList(Hash32)),  # allow for a log-sized Merkle proof from any block to any historical block root"  # noqa: E501

        # PoW receipt root
        ('processed_pow_receipt_root', hash32),
        ('candidate_pow_receipt_roots', CountableList(CandidatePoWReceiptRootRecord)),
    ]

    def __init__(
            self,
            slot: int,
            genesis_time: int,
            fork_data: ForkData,
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
            validator_registry: Sequence[ValidatorRecord]=(),
            shard_committees_at_slots: Sequence[Sequence[ShardCommittee]]=(),
            persistent_committees: Sequence[Sequence[int]]=(),
            persistent_committee_reassignments: Sequence[ShardReassignmentRecord]=(),
            latest_crosslinks: Sequence[CrosslinkRecord]=(),
            latest_block_roots: Sequence[Hash32]=(),
            latest_penalized_exit_balances: Sequence[int]=(),
            batched_block_roots: Sequence[Hash32]=(),
            latest_attestations: Sequence[PendingAttestationRecord]=(),
            candidate_pow_receipt_roots: Sequence[CandidatePoWReceiptRootRecord]=()
    ) -> None:
        super().__init__(
            # Misc
            slot=slot,
            genesis_time=genesis_time,
            fork_data=fork_data,
            # Validator registry
            validator_registry=validator_registry,
            validator_registry_latest_change_slot=validator_registry_latest_change_slot,
            validator_registry_exit_count=validator_registry_exit_count,
            validator_registry_delta_chain_tip=validator_registry_delta_chain_tip,
            # Randomness and committees
            randao_mix=randao_mix,
            next_seed=next_seed,
            shard_committees_at_slots=shard_committees_at_slots,
            persistent_committees=persistent_committees,
            persistent_committee_reassignments=persistent_committee_reassignments,
            # Finality
            previous_justified_slot=previous_justified_slot,
            justified_slot=justified_slot,
            justification_bitfield=justification_bitfield,
            finalized_slot=finalized_slot,
            # Recent state
            latest_crosslinks=latest_crosslinks,
            latest_block_roots=latest_block_roots,
            latest_penalized_exit_balances=latest_penalized_exit_balances,
            latest_attestations=latest_attestations,
            batched_block_roots=batched_block_roots,
            # PoW receipt root
            processed_pow_receipt_root=processed_pow_receipt_root,
            candidate_pow_receipt_roots=candidate_pow_receipt_roots,
        )

    def __repr__(self) -> str:
        return 'BeaconState #{0}>'.format(
            encode_hex(self.root)[2:10],
        )

    _hash = None

    @property
    def hash(self) -> Hash32:
        if self._hash is None:
            self._hash = hash_eth2(rlp.encode(self))
        return self._hash

    @property
    def root(self) -> Hash32:
        # Alias of `hash`.
        # Using flat hash, might change to SSZ tree hash.
        return self.hash

    @property
    def num_validators(self) -> int:
        return len(self.validator_registry)

    @property
    def num_crosslinks(self) -> int:
        return len(self.latest_crosslinks)
