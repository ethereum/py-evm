from eth.vm.forks.muir_glacier.state import (
    MuirGlacierState
)

from .computation import BerlinComputation

from eth_typing import Address


class BerlinState(MuirGlacierState):
    computation_class = BerlinComputation

    def mark_account_accessed(self, address: Address) -> None:
        self.add_account_accessed(address)

    def is_account_accessed(self, address: Address) -> bool:
        return address in self.get_access_list()

    def mark_storage_accessed(self, address: Address, slot: int) -> None:
        pass

    def is_storage_accessed(self, address: Address, slot: int) -> None:
        pass
