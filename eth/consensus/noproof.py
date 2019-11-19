from eth.abc import (
    AtomicDatabaseAPI,
    VirtualMachineAPI,
    VirtualMachineModifierAPI,
)
from eth.typing import (
    VMConfiguration,
)


class NoProofConsensus(VirtualMachineModifierAPI):
    """
    Modify a set of VMs to accept blocks without any validation.
    """

    def __init__(self, base_db: AtomicDatabaseAPI) -> None:
        pass

    @classmethod
    def amend_vm_configuration_for_chain_class(cls, config: VMConfiguration) -> None:
        """
        Amend the given ``VMConfiguration`` to operate under the default POW rules.
        """
        for pair in config:
            block_number, vm = pair
            setattr(vm, 'validate_seal', lambda *_: None)

    def amend_vm_for_chain_instance(self, vm: VirtualMachineAPI) -> None:
        setattr(vm, 'validate_seal', lambda *_: None)
