import rlp

from eth.rlp.sedes import (
    uint64,
)


class ForkData(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Previous fork version
        ('pre_fork_version', uint64),
        # Post fork version
        ('post_fork_version', uint64),
        # Fork slot number
        ('fork_slot', uint64)
    ]

    def __init__(self,
                 pre_fork_version: int,
                 post_fork_version: int,
                 fork_slot: int) -> None:
        super().__init__(
            pre_fork_version=pre_fork_version,
            post_fork_version=post_fork_version,
            fork_slot=fork_slot,
        )
