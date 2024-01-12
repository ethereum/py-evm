import logging
from typing import (
    Iterable,
    Sequence,
)

from eth_typing import (
    Address,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    to_tuple,
)

from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
    ConsensusAPI,
    ConsensusContextAPI,
    VirtualMachineAPI,
    VirtualMachineModifierAPI,
)
from eth.db.chain import (
    ChainDB,
)
from eth.typing import (
    HeaderParams,
    VMConfiguration,
    VMFork,
)

from ._utils import (
    get_block_signer,
    is_in_turn,
    validate_header_integrity,
)
from .constants import (
    EPOCH_LENGTH,
)
from .datatypes import (
    Snapshot,
)
from .snapshot_manager import (
    SnapshotManager,
)


def configure_header(
    vm: VirtualMachineAPI, **header_params: HeaderParams
) -> BlockHeaderAPI:
    with vm.get_header().build_changeset(**header_params) as changeset:
        # We do this because the default `configure_header` tries to compute the
        # difficulty which we can not do at this point. We take the `difficulty` as
        # provided and rely on the `validate_seal` call that will happen as the last
        # step when blocks are imported.
        header = changeset.commit()
    return header


def _construct_turn_error_message(
    expected_difficulty: int,
    header: BlockHeaderAPI,
    signer: Address,
    signers: Sequence[Address],
) -> str:
    return (
        f"Expected difficulty of {header} to be {expected_difficulty} "
        f"but was {header.difficulty}.\n"
        f"Header signer: {encode_hex(signer)}. Valid signers: {signers}"
    )


class CliqueConsensusContext(ConsensusContextAPI):
    epoch_length = EPOCH_LENGTH

    def __init__(self, db: AtomicDatabaseAPI):
        self.db = db
        self.snapshot_manager = SnapshotManager(ChainDB(db), self.epoch_length)


class CliqueConsensus(ConsensusAPI):
    """
    This class is the entry point to operate a chain under the rules of Clique consensus
    which is defined in EIP-225: https://eips.ethereum.org/EIPS/eip-225
    """

    logger = logging.getLogger("eth.consensus.clique.CliqueConsensus")

    def __init__(self, context: CliqueConsensusContext) -> None:
        if context is None:
            raise ValueError("Can not instantiate without `context`")
        self._epoch_length = context.epoch_length
        self._snapshot_manager = context.snapshot_manager

    @classmethod
    def get_fee_recipient(cls, header: BlockHeaderAPI) -> Address:
        """
        If the ``header`` has a signer, return the signer, otherwise return the
        ``coinbase`` of the passed header.
        """
        try:
            return get_block_signer(header)
        except ValueError:
            return header.coinbase

    def get_snapshot(self, header: BlockHeaderAPI) -> Snapshot:
        """
        Retrieve the ``Snapshot`` for the given ``header``.
        """
        return self._snapshot_manager.get_or_create_snapshot(
            header.block_number, header.hash
        )

    def validate_seal(self, header: BlockHeaderAPI) -> None:
        """
        Only validate the integrity of the header, use `validate_seal_extension`
        to validate the consensus relevant seal of the header.
        """
        validate_header_integrity(header, self._epoch_length)

    def validate_seal_extension(
        self, header: BlockHeaderAPI, parents: Iterable[BlockHeaderAPI]
    ) -> None:
        """
        Validate the seal of the given ``header`` according
        to the Clique consensus rules.
        """
        if header.block_number == 0:
            return

        validate_header_integrity(header, self._epoch_length)

        signer = get_block_signer(header)
        snapshot = self._snapshot_manager.get_or_create_snapshot(
            header.block_number - 1, header.parent_hash, parents
        )
        in_turn = is_in_turn(signer, snapshot, header)

        authorized_signers = snapshot.get_sorted_signers()

        if in_turn and header.difficulty != 2:
            raise ValidationError(
                _construct_turn_error_message(2, header, signer, authorized_signers)
            )
        elif not in_turn and header.difficulty != 1:
            raise ValidationError(
                _construct_turn_error_message(1, header, signer, authorized_signers)
            )

        self._snapshot_manager.apply(snapshot, header)

        if signer not in authorized_signers:
            raise ValidationError(
                f"Failed to validate {header}."
                f"Signer {encode_hex(signer)} not in {authorized_signers}"
            )


class CliqueApplier(VirtualMachineModifierAPI):
    """
    This class is used to apply a clique consensus engine
    to a series of virtual machines
    """

    @to_tuple
    def amend_vm_configuration(self, config: VMConfiguration) -> Iterable[VMFork]:
        """
        Amend the given ``VMConfiguration`` to operate
        under the rules of Clique consensus.
        """
        for pair in config:
            block_number, vm = pair
            vm_class = vm.configure(
                extra_data_max_bytes=65535,
                consensus_class=CliqueConsensus,
                configure_header=configure_header,
                get_block_reward=staticmethod(int),
                get_uncle_reward=staticmethod(int),
            )

            yield block_number, vm_class
