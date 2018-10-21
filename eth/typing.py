from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    NewType,
    Tuple,
    Union,
)

from eth_typing import (
    Address,
)
from mypy_extensions import (
    TypedDict,
)


# TODO: Move into eth_typing

AccountDetails = TypedDict('AccountDetails',
                           {'balance': int,
                            'nonce': int,
                            'code': bytes,
                            'storage': Dict[int, int]
                            })
AccountState = Dict[Address, AccountDetails]

AccountDiff = Iterable[Tuple[Address, str, Union[int, bytes], Union[int, bytes]]]

GeneralState = Union[
    AccountState,
    List[Tuple[Address, Dict[str, Union[int, bytes, Dict[int, int]]]]]
]

TransactionDict = TypedDict('TransactionDict',
                            {'nonce': int,
                             'gasLimit': int,
                             'gasPrice': int,
                             'to': Address,
                             'value': int,
                             'data': bytes,
                             'secretKey': bytes,
                             })

NormalizerType = Callable[[Dict[Any, Any]], Dict[str, Any]]

TransactionNormalizer = Callable[[TransactionDict], TransactionDict]

VRS = NewType("VRS", Tuple[int, int, int])
