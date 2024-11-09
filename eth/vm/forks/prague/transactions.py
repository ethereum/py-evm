from abc import (
    ABC,
)
from typing import (
    Type,
)

import rlp

from eth.abc import (
    SignedTransactionAPI,
)
from eth.rlp.transactions import (
    SignedTransactionMethods,
)
from eth.vm.forks.berlin.transactions import (
    TypedTransaction,
)
from eth.vm.forks.cancun.transactions import (
    CancunLegacyTransaction,
    CancunTransactionBuilder,
    CancunUnsignedLegacyTransaction,
)


class PragueLegacyTransaction(CancunLegacyTransaction, ABC):
    pass


class PragueUnsignedLegacyTransaction(CancunUnsignedLegacyTransaction):
    pass


class SetCodeTransaction(
    rlp.Serializable, SignedTransactionMethods, SignedTransactionAPI
):
    pass


class PragueTypedTransaction(TypedTransaction):
    pass


class PragueTransactionBuilder(CancunTransactionBuilder):
    legacy_signed = PragueLegacyTransaction
    legacy_unsigned = PragueUnsignedLegacyTransaction
    typed_transaction: Type[TypedTransaction] = PragueTypedTransaction
