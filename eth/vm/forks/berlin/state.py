from eth.vm.forks.muir_glacier.state import (
    MuirGlacierState
)

from .computation import BerlinComputation


class BerlinState(MuirGlacierState):
    computation_class = BerlinComputation

    def mark_account_accessed(self, account):
        self.add_account_accessed(account)

    def is_account_accessed(self, account):
        return account in self.get_access_list()

    def _lock_changes(self):
        self.lock_changes()

    def mark_storage_accessed(self, account, slot):
        pass

    def is_storage_accessed(self, account, slot):
        pass
