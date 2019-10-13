import logging
from typing import Sequence, Iterable

from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
    VirtualMachineAPI,
)
from eth.db.chain import ChainDB

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    encode_hex,
    to_tuple,
    ValidationError,
)

from eth.typing import (
    HeaderParams,
    VMConfiguration,
    VMFork,
)
from eth.vm.chain_context import ChainContext
from eth.vm.execution_context import (
    ExecutionContext,
)

from .constants import (
    EPOCH_LENGTH,
)
from .datatypes import (
    Snapshot,
)
from .header_cache import HeaderCache
from .snapshot_manager import SnapshotManager
from ._utils import (
    get_block_signer,
    is_in_turn,
    validate_header_integrity,
)


def configure_header(vm: VirtualMachineAPI, **header_params: HeaderParams) -> BlockHeaderAPI:
    with vm.get_header().build_changeset(**header_params) as changeset:
        # We do this because the default `configure_header` tries to compute the difficulty
        # which we can not do at this point. We take the `difficulty` as provided and rely
        # on the `validate_seal` call that will happen as the last step when blocks are
        # imported.
        header = changeset.commit()
    return header


def _construct_turn_error_message(expected_difficulty: int,
                                  header: BlockHeaderAPI,
                                  signer: Address,
                                  signers: Sequence[Address]) -> str:

    return (
        f"Expected difficulty of {header} to be {expected_difficulty} "
        f"but was {header.difficulty}.\n"
        f"Header signer: {encode_hex(signer)}. Valid signers: {signers}"
    )


class CliqueConsensus:
    """
    This class is the entry point to operate a chain under the rules of Clique consensus which
    is defined in EIP-225: https://eips.ethereum.org/EIPS/eip-225
    """

    logger = logging.getLogger('eth.consensus.clique.CliqueConsensus')

    def __init__(self, base_db: AtomicDatabaseAPI, epoch_length: int = EPOCH_LENGTH) -> None:
        if base_db is None:
            raise ValueError("Can not instantiate without `base_db`")
        self._epoch_length = epoch_length
        self._chain_db = ChainDB(base_db)
        self._header_cache = HeaderCache(self._chain_db)
        self._snapshot_manager = SnapshotManager(
            self._chain_db,
            self._header_cache,
            self._epoch_length,
        )

    @to_tuple
    def amend_vm_configuration(self, config: VMConfiguration) -> Iterable[VMFork]:
        """
        Amend the given ``VMConfiguration`` to operate under the rules of Clique consensus.
        """
        for pair in config:
            block_number, vm = pair
            vm_class = vm.configure(
                extra_data_max_bytes=65535,
                validate_seal=staticmethod(self.validate_seal),
                create_execution_context=staticmethod(self.create_execution_context),
                configure_header=configure_header,
                _assign_block_rewards=lambda _, __: None,
            )

            yield block_number, vm_class

    @staticmethod
    def create_execution_context(header: BlockHeaderAPI,
                                 prev_hashes: Iterable[Hash32],
                                 chain_context: ChainContext) -> ExecutionContext:

        # In Clique consensus, the tx fee goes to the signer
        try:
            coinbase = get_block_signer(header)
        except ValueError:
            coinbase = header.coinbase

        return ExecutionContext(
            coinbase=coinbase,
            timestamp=header.timestamp,
            block_number=header.block_number,
            difficulty=header.difficulty,
            gas_limit=header.gas_limit,
            prev_hashes=prev_hashes,
            chain_id=chain_context.chain_id,
        )

    def get_snapshot(self, header: BlockHeaderAPI) -> Snapshot:
        """
        Retrieve the ``Snapshot`` for the given ``header``.
        """
        return self._snapshot_manager.get_or_create_snapshot(header.block_number, header.hash)

    def validate_seal(self, header: BlockHeaderAPI) -> None:
        """
        Validate the seal of the given ``header`` according to the Clique consensus rules.
        """
        if header.block_number == 0:
            return

        validate_header_integrity(header, self._epoch_length)

        self._header_cache[header.hash] = header

        signer = get_block_signer(header)
        snapshot = self._snapshot_manager.get_or_create_snapshot(
            header.block_number - 1, header.parent_hash)
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

        self._header_cache.evict()
