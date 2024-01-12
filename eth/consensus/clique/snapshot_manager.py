from typing import (
    Iterable,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    get_extended_debug_logger,
)
import lru

from eth.abc import (
    BlockHeaderAPI,
    ChainDatabaseAPI,
)
from eth.exceptions import (
    HeaderNotFound,
)

from ._utils import (
    get_block_signer,
    get_signers_at_checkpoint,
    is_checkpoint,
)
from .constants import (
    IN_MEMORY_SNAPSHOTS,
    NONCE_AUTH,
    NONCE_DROP,
)
from .datatypes import (
    MutableSnapshot,
    Snapshot,
    Tally,
    Vote,
    VoteAction,
)
from .encoding import (
    decode_snapshot,
    encode_snapshot,
)
from .exceptions import (
    SnapshotNotFound,
)


def make_snapshot_lookup_key(block_hash: Hash32) -> bytes:
    return f"block-hash-to-snapshot:{block_hash}".encode()


class SnapshotManager:
    """
    The ``SnapshotManager`` is responsible for managing the snapshots that hold the
    current state of the consensus engine. It creates new snapshots by applying headers
    on top of existing snapshots. It comes with APIs to create,
    persist and retrieve snapshots.
    """

    logger = get_extended_debug_logger(
        "eth.consensus.clique.snapshot_manager.SnapshotManager"
    )

    def __init__(self, chain_db: ChainDatabaseAPI, epoch_length: int) -> None:
        self._chain_db = chain_db
        self._epoch_length = epoch_length
        self._snapshots: lru.LRU[Hash32, Snapshot] = lru.LRU(IN_MEMORY_SNAPSHOTS)

    def _lookup_header(
        self, block_hash: Hash32, parents: Iterable[BlockHeaderAPI]
    ) -> BlockHeaderAPI:
        for parent in parents:
            if parent.hash == block_hash:
                return parent
        try:
            return self._chain_db.get_block_header_by_hash(block_hash)
        except HeaderNotFound:
            raise ValidationError(f"Unknown ancestor {encode_hex(block_hash)}")

    def _create_snapshot_from_checkpoint_header(
        self, header: BlockHeaderAPI
    ) -> Snapshot:
        signers = get_signers_at_checkpoint(header)
        self.logger.debug2(f"Created snapshot from checkpoint at {header}")

        snapshot = MutableSnapshot(
            signers=list(signers), block_hash=header.hash, votes=[], tallies={}
        )
        return self.add_snapshot(snapshot)

    def apply(self, current_snapshot: Snapshot, header: BlockHeaderAPI) -> Snapshot:
        """
        Apply the given header on top of the current snapshot to create a new snapshot.
        """
        if is_checkpoint(header.block_number, self._epoch_length):
            return self._create_snapshot_from_checkpoint_header(header)

        snapshot = current_snapshot.get_mutable_clone(header.hash)

        if header.nonce in {NONCE_AUTH, NONCE_DROP}:
            signer = get_block_signer(header)
            # Clear any votes from the signer regarding the subject that is voted on
            for vote in snapshot.votes:
                if vote.signer == signer and vote.subject == header.coinbase:
                    self.retract_vote(snapshot, vote.subject, vote.action)
                    snapshot.votes.remove(vote)
                    break

            action = VoteAction(header.nonce)

            if self.cast_vote(snapshot, header.coinbase, action):
                vote = Vote(
                    signer=signer,
                    block_number=header.block_number,
                    subject=header.coinbase,
                    action=action,
                )
                snapshot.votes.append(vote)

                tally = snapshot.tallies[header.coinbase]
                if tally.votes > len(snapshot.signers) / 2:
                    if tally.action is VoteAction.NOMINATE:
                        snapshot.signers.append(header.coinbase)
                        self.logger.debug(f"New signer added: {header.coinbase}")
                    else:
                        if header.coinbase in snapshot.signers:
                            snapshot.signers.remove(header.coinbase)
                            self.logger.debug(f"Signer removed: {header.coinbase}")

                    for vote in snapshot.votes.copy():
                        # Discard any pending votes *from* the added or removed member
                        if vote.signer == header.coinbase:
                            if self.retract_vote(snapshot, vote.subject, vote.action):
                                snapshot.votes.remove(vote)

                        # Discard any pending votes *regarding* the added or
                        # removed member. No need to uncast, the whole tally is going
                        # to be removed anyway.
                        if vote.subject == header.coinbase:
                            snapshot.votes.remove(vote)

                    snapshot.tallies.pop(header.coinbase)

        self.add_snapshot(snapshot)

        return snapshot.get_immutable_clone()

    def get_or_create_snapshot(
        self,
        block_number: int,
        block_hash: Hash32,
        parents: Iterable[BlockHeaderAPI] = (),
    ) -> Snapshot:
        """
        Return a snapshot either by creating or retrieving it or raise a
        ``ValidationError`` if the header does not have a known ancestor.
        """
        try:
            snapshot = self.get_snapshot(block_number, block_hash)
        except SnapshotNotFound:
            return self.create_snapshot_for(block_hash, parents)
        else:
            return snapshot

    def create_snapshot_for(
        self, block_hash: Hash32, cached_parents: Iterable[BlockHeaderAPI]
    ) -> Snapshot:
        """
        Create a ``Snapshot`` for the given ``block_hash``. This involves traversing
        backwards through the chain of headers to find a suitable base snapshot either
        from memory, on disk or by creating it on the fly from a checkpoint header.
        After we've found a suitable base snapshot, apply all headers from after the
        base snapshot up to the header of ``block_hash`` to create the requested
        snapshot.
        """
        current_header = header = self._lookup_header(block_hash, cached_parents)

        if is_checkpoint(header.block_number, self._epoch_length):
            return self._create_snapshot_from_checkpoint_header(current_header)

        parents = []
        while True:
            try:
                new_snapshot = self.get_snapshot(
                    current_header.block_number, current_header.parent_hash
                )
            except SnapshotNotFound:
                current_header = self._lookup_header(
                    current_header.parent_hash, cached_parents
                )

                if is_checkpoint(current_header.block_number, self._epoch_length):
                    new_snapshot = self._create_snapshot_from_checkpoint_header(
                        current_header
                    )
                    break
                else:
                    parents.append(current_header)
            else:
                break

        for parent in reversed(parents):
            new_snapshot = self.apply(new_snapshot, parent)

        new_snapshot = self.apply(new_snapshot, header)

        if is_checkpoint(header.block_number, self._epoch_length):
            self.logger.debug2(
                f"Persisting checkpoint snapshot at {header.block_number}",
            )
            self.persist_snapshot(new_snapshot)

        return new_snapshot

    def get_snapshot(self, block_number: int, block_hash: Hash32) -> Snapshot:
        """
        Return a ``Snapshot`` if it exists in memory, on-disk or can be computed
        directly from a header that serves as a checkpoint.
        Otherwise raise a ``SnapshotNotFound`` error.
        """
        # We first try to find the snapshot in memory
        if block_hash in self._snapshots:
            return self._snapshots[block_hash]

        if is_checkpoint(block_number, self._epoch_length):
            try:
                # We might have it saved on disk
                return self.get_snapshot_from_db(block_hash)
            except SnapshotNotFound:
                pass

            try:
                # Otherwise, we can retrieve it on the fly
                header = self._chain_db.get_block_header_by_hash(block_hash)
            except HeaderNotFound:
                raise SnapshotNotFound(
                    f"Can not get snapshot for {block_hash!r} at {block_number}"
                )
            else:
                if header.block_number != block_number:
                    raise SnapshotNotFound(
                        f"Can not get snapshot for {block_hash!r} at {block_number}"
                    )
                else:
                    return self._create_snapshot_from_checkpoint_header(header)

        raise SnapshotNotFound(
            f"Can not get snapshot for {block_hash!r} at {block_number}"
        )

    def add_snapshot(self, mutable_snapshot: MutableSnapshot) -> Snapshot:
        """
        Retrieve a ``Snapshot`` from the given ``mutable_snapshot``
        and add it to the local cache.
        """
        snapshot = mutable_snapshot.get_immutable_clone()
        self._snapshots[snapshot.block_hash] = snapshot
        return snapshot

    def persist_snapshot(self, snapshot: Snapshot) -> None:
        """
        Persist the given snapshot to the database.
        """
        key = make_snapshot_lookup_key(snapshot.block_hash)
        with self._chain_db.db.atomic_batch() as db:
            db[key] = encode_snapshot(snapshot)

    def get_snapshot_from_db(self, block_hash: Hash32) -> Snapshot:
        """
        Retrieve a snapshot from the database.
        Raise ``SnapshotNotFound`` if it does not exist.
        """
        key = make_snapshot_lookup_key(block_hash)
        try:
            encoded_key = self._chain_db.db[key]
        except KeyError as e:
            raise SnapshotNotFound(
                f"Can not get on-disk snapshot for {block_hash!r}"
            ) from e
        else:
            return decode_snapshot(encoded_key)

    def cast_vote(
        self, snapshot: MutableSnapshot, subject: Address, action: VoteAction
    ) -> bool:
        """
        Cast a vote on a ``MutableSnapshot``.
        """
        try:
            action.validate_for(snapshot.signers, subject)
        except ValidationError:
            return False

        if subject not in snapshot.tallies:
            snapshot.tallies[subject] = Tally(action)

        snapshot.tallies[subject] = snapshot.tallies[subject].upvote()
        return True

    def retract_vote(
        self, snapshot: MutableSnapshot, subject: Address, action: VoteAction
    ) -> bool:
        """
        Retract a vote on a ``MutableSnapshot``.
        """
        if subject not in snapshot.tallies:
            # Dangling votes are simply dropped
            return True

        tally = snapshot.tallies[subject]

        if tally.action is not action:
            return False

        if tally.votes > 1:
            snapshot.tallies[subject] = tally.downvote()
        else:
            snapshot.tallies.pop(subject)

        return True
