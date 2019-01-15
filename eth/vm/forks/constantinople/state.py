from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_SHA3,
)
from eth.exceptions import StateRootNotFound
from eth.typing import (
    BaseOrSpoofTransaction,
    Tuple,
)
from eth.vm.computation import (
    BaseComputation,
)
from eth.vm.forks.byzantium.state import (
    ByzantiumState
)

from .computation import ConstantinopleComputation


class ConstantinopleState(ByzantiumState):
    computation_class = ConstantinopleComputation

    def apply_transaction(self, transaction: BaseOrSpoofTransaction) -> \
            Tuple[bytes, BaseComputation]:
        if self.state_root != BLANK_ROOT_HASH and not self.account_db.has_root(self.state_root):
            raise StateRootNotFound(self.state_root)
        computation = self.execute_transaction(transaction)
        return EMPTY_SHA3, computation
