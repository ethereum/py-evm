import cachetools.func

from typing import (
    Type
)
from eth_utils import (
    ValidationError,
)

from eth.chains.base import (
    BaseChain
)
from eth.rlp.transactions import (
    BaseTransaction,
    BaseTransactionFields
)


class DefaultTransactionValidator():
    """
    The :class:`~trinity.tx_pool.validators.DefaultTransactionValidator` class is responsible to
    decide wether transactions should be relayed to peers or not. This implementation validates
    transactions against a transaction class inferred from a ``initial_tx_validation_block_number``
    but will switch to a different one as soon as the tip of the chain uses a more up to date
    transaction class than the one that corresponds to the ``initial_tx_validation_block_number``.
    """

    def __init__(self, chain: BaseChain, initial_tx_validation_block_number: int) -> None:
        self.chain = chain
        self._initial_tx_class = self._get_tx_class_for_block_number(
            initial_tx_validation_block_number
        )
        self._ordered_tx_classes = [
            vm_class.get_transaction_class()
            for _, vm_class in chain.get_vm_configuration()
        ]
        self._initial_tx_class_index = self._ordered_tx_classes.index(self._initial_tx_class)

    def __call__(self, transaction: BaseTransactionFields) -> bool:

        transaction_class = self.get_appropriate_tx_class()
        tx = transaction_class(**transaction.as_dict())
        try:
            tx.validate()
        except ValidationError:
            return False
        else:
            return True

    @cachetools.func.ttl_cache(maxsize=1024, ttl=300)
    def get_appropriate_tx_class(self) -> Type[BaseTransaction]:
        head = self.chain.get_canonical_head()
        current_tx_class = self.chain.get_vm_class(head).get_transaction_class()
        # If the current head of the chain is still on a fork that is before the currently
        # active fork (syncing), ensure that we use the specified initial tx class
        if self._is_outdated_tx_class(current_tx_class):
            return self._initial_tx_class

        return current_tx_class

    def _is_outdated_tx_class(self, tx_class: Type[BaseTransaction]) -> bool:
        return self._ordered_tx_classes.index(tx_class) < self._initial_tx_class_index

    def _get_tx_class_for_block_number(self, block_number: int) -> Type[BaseTransaction]:
        vm_class = self.chain.get_vm_class_for_block_number(block_number)
        return vm_class.get_transaction_class()
