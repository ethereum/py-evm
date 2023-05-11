from enum import (
    Enum,
)
from typing import (
    Dict,
    FrozenSet,
    List,
    NamedTuple,
    Sequence,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from .constants import (
    NONCE_AUTH,
    NONCE_DROP,
)


class VoteAction(Enum):
    """
    The action that is being voted on (nominate or kick).
    """

    # Using the byte representation rather than auto()
    # makes serialization more convenient
    NOMINATE = NONCE_AUTH
    KICK = NONCE_DROP

    def validate_for(self, signers: Sequence[Address], subject: Address) -> None:
        """
        Check if a vote action is semantically valid, meaning it is either voting
        against an existing member or voting in favor of an address that is not
        yet a member.
        """
        signer_exists = subject in signers
        signer_is_kicked = signer_exists and self is VoteAction.KICK
        signer_is_nominated = not signer_exists and self is VoteAction.NOMINATE

        if not signer_is_kicked and not signer_is_nominated:
            raise ValidationError(
                "Must either kick an existing signer or nominate a new signer"
                f"Subject: {subject!r} Current signers: {signers}"
            )


class Tally(NamedTuple):
    """
    Represent a tally to track votes on new members getting signed in or out.
    """

    action: VoteAction
    votes: int = 0

    def upvote(self) -> "Tally":
        return Tally(self.action, self.votes + 1)

    def downvote(self) -> "Tally":
        return Tally(self.action, self.votes - 1)


class Vote(NamedTuple):
    """
    Represent a vote (nominate/kick) from a signer regarding a subject.
    """

    signer: Address
    block_number: int
    subject: Address
    action: VoteAction


class Snapshot(NamedTuple):
    """
    Represent the current state of the consensus at a given time. This
    includes all current signers, all current votes as well at all tallies.
    """

    signers: FrozenSet[Address]
    block_hash: Hash32
    votes: FrozenSet[Vote]
    # Unfortunately there's no FrozenDict but at least Address and Tally
    # are both immutable
    tallies: Dict[Address, Tally]

    def get_mutable_clone(self, block_hash: Hash32) -> "MutableSnapshot":
        """
        Return a ``MutableSnapshot`` snapshot clone that can be used as a work in
        progress representation of the snapshot.
        """
        return MutableSnapshot(
            signers=list(self.signers),
            block_hash=block_hash,
            votes=list(self.votes),
            tallies=self.tallies.copy(),
        )

    def get_sorted_signers(self) -> List[Address]:
        """
        Return the sorted list of signers.
        """
        return sorted(self.signers)


class MutableSnapshot(NamedTuple):
    """
    Like ``Snapshot`` but mutable as a work in progress representation.
    """

    signers: List[Address]
    block_hash: Hash32
    votes: List[Vote]
    tallies: Dict[Address, Tally]

    def get_immutable_clone(self) -> Snapshot:
        """
        Return a ``Snapshot``, an immutable clone of the mutable snapshot.
        """
        return Snapshot(
            signers=frozenset(self.signers),
            block_hash=self.block_hash,
            votes=frozenset(self.votes),
            tallies=self.tallies.copy(),
        )
