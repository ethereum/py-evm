import collections
import operator
from typing import (
    Any,
    Generator,
    Sequence,
    Tuple,
    Type,
    Union,
)

from eth_typing import BlockNumber
from eth_utils.toolz import (
    assoc,
    last,
)

from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.abc import (
    BlockHeaderAPI,
    VirtualMachineAPI,
)
from eth.constants import GENESIS_BLOCK_NUMBER
from eth.chains.base import Chain
from eth.chains.mainnet import MainnetChain
from eth.validation import (
    validate_gte,
)
from eth.vm.forks.homestead import HomesteadVM


class MaintainGasLimitMixin:
    @classmethod
    def create_header_from_parent(
        cls, parent_header: BlockHeaderAPI, **header_params: Any
    ) -> "MaintainGasLimitMixin":
        """
        Call the parent class method maintaining the same gas_limit as the
        previous block.
        """
        return super().create_header_from_parent(  # type: ignore
            parent_header, **assoc(header_params, "gas_limit", parent_header.gas_limit)
        )


MAINNET_VMS = collections.OrderedDict(
    (vm_class.fork, type(vm_class.__name__, (MaintainGasLimitMixin, vm_class), {}))
    for _, vm_class in MainnetChain.vm_configuration
)

ForkStartBlocks = Sequence[Tuple[BlockNumber, Union[str, Type[VirtualMachineAPI]]]]
VMStartBlock = Tuple[BlockNumber, Type[VirtualMachineAPI]]


@to_tuple
def _generate_vm_configuration(
    *fork_start_blocks: ForkStartBlocks, dao_start_block: Union[int, bool] = None
) -> Generator[VMStartBlock, None, None]:
    """
    fork_start_blocks should be 2-tuples of (start_block, fork_name_or_vm_class)

    dao_start_block determines whether the Homestead fork will support the DAO
    fork and if so, at what block.

        - dao_start_block = None: perform the DAO fork at the same block as the
          Homestead start block.
        - dao_start_block = False: do not perform the DAO fork.
        - dao_start_block = <int>: perform the DAO fork at the given block number.
    """
    # if no configuration was passed in, initialize the chain with the *latest*
    # Mainnet VM rules active at block 0.
    if not fork_start_blocks:
        yield (GENESIS_BLOCK_NUMBER, last(MAINNET_VMS.values()))
        return

    # Validate that there are no fork names which are not represented in the
    # mainnet chain.
    fork_names = {
        fork_name for _, fork_name in fork_start_blocks if isinstance(fork_name, str)
    }
    unknown_forks = sorted(fork_names.difference(MAINNET_VMS.keys()))
    if unknown_forks:
        raise ValidationError(f"Configuration contains unknown forks: {unknown_forks}")

    # Validate that *if* an explicit value was passed in for dao_start_block
    # that the Homestead fork rules are part of the VM configuration.
    if dao_start_block is not None and "homestead" not in fork_names:
        raise ValidationError(
            "The `dao_start_block` parameter is only valid for the 'homestead' "
            "fork rules.  The 'homestead' VM was not included in the provided "
            "fork configuration"
        )

    # If no VM is set to start at block 0, default to the frontier VM
    start_blocks = {start_block for start_block, _ in fork_start_blocks}
    if 0 not in start_blocks:
        yield GENESIS_BLOCK_NUMBER, MAINNET_VMS["frontier"]

    ordered_fork_start_blocks = sorted(fork_start_blocks, key=operator.itemgetter(0))

    # Iterate over the parameters, generating a tuple of 2-tuples in the form:
    # (start_block, vm_class)
    for start_block, fork in ordered_fork_start_blocks:
        if isinstance(fork, type) and issubclass(fork, VirtualMachineAPI):
            vm_class = fork
        elif isinstance(fork, str):
            vm_class = MAINNET_VMS[fork]
        else:
            raise Exception("Invariant: unreachable code path")

        if issubclass(vm_class, HomesteadVM):
            if dao_start_block is False:
                yield (start_block, vm_class.configure(support_dao_fork=False))
            elif dao_start_block is None:
                yield (
                    start_block,
                    vm_class.configure(_dao_fork_block_number=start_block),
                )
            elif isinstance(dao_start_block, int):
                validate_gte(dao_start_block, start_block)
                yield (
                    start_block,
                    vm_class.configure(_dao_fork_block_number=dao_start_block),
                )
            else:
                raise Exception("Invariant: unreachable code path")
        else:
            yield (start_block, vm_class)


class BaseMainnetTesterChain(Chain):
    vm_configuration: Tuple[
        Tuple[BlockNumber, Type[VirtualMachineAPI]], ...
    ] = _generate_vm_configuration()


class MainnetTesterChain(BaseMainnetTesterChain):
    """
    This class is intended to be used for in-memory test chains.  It
    explicitely bypasses the proof of work validation to allow for instant
    block mining.

    It exposes one additional API `configure_forks` to allow for in-flight
    configuration of fork rules.
    """

    def validate_seal(self, header: BlockHeaderAPI) -> None:
        """
        We don't validate the proof of work seal on the tester chain.
        """
        pass

    def configure_forks(
        self,
        *fork_start_blocks: ForkStartBlocks,
        dao_start_block: Union[int, bool] = None,
    ) -> None:
        """
        On demand configuration of fork rules.  This is a foot gun that if used
        incorrectly could cause weird VM errors.

        It should generally only be used on a genesis chain (head block == 0).
        Modifying the fork rules, especially if the modification effects
        existing blocks could result in a broken chain.
        """
        self.vm_configuration = _generate_vm_configuration(
            *fork_start_blocks,
            dao_start_block=dao_start_block,
        )
