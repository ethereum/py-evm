from typing import (
    Iterable,
    Type,
)

from eth_utils import (
    to_tuple,
)

from eth.abc import (
    ConsensusAPI,
    VirtualMachineModifierAPI,
    VMConfiguration,
)
from eth.typing import (
    VMFork,
)


class ConsensusApplier(VirtualMachineModifierAPI):
    """
    This class is used to apply simple types of consensus engines to a series of
    virtual machines.

    Note that this *must not* be used for Clique, which has its own modifier
    """

    def __init__(self, consensus_class: Type[ConsensusAPI]) -> None:
        self._consensus_class = consensus_class

    @to_tuple
    def amend_vm_configuration(self, config: VMConfiguration) -> Iterable[VMFork]:
        """
        Amend the given ``VMConfiguration`` to operate
        under the rules of the pre-defined consensus
        """
        for pair in config:
            block_number, vm = pair
            yield block_number, vm.configure(consensus_class=self._consensus_class)
