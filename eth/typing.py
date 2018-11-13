from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    NewType,
    Tuple,
    Union,
    TypeVar,
    TYPE_CHECKING,
)

from eth_typing import (
    Address,
    HexStr,
)
from mypy_extensions import (
    TypedDict,
)

if TYPE_CHECKING:
    from eth.rlp.transactions import (  # noqa: F401
        BaseTransaction
    )
    from eth.utils.spoof import (  # noqa: F401
        SpoofTransaction
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

BaseOrSpoofTransaction = Union['BaseTransaction', 'SpoofTransaction']

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

Normalizer = Callable[[Dict[Any, Any]], Dict[str, Any]]

TransactionNormalizer = Callable[[TransactionDict], TransactionDict]

VRS = NewType("VRS", Tuple[int, int, int])

IntConvertible = Union[int, bytes, HexStr, str]


TFunc = TypeVar('TFunc')


class StaticMethod(Generic[TFunc]):
    """
    A property class purely to convince mypy to let us assign a function to an
    instance variable. See more at: https://github.com/python/mypy/issues/708#issuecomment-405812141
    """
    def __get__(self, oself: Any, owner: Any) -> TFunc:
        return self._func

    def __set__(self, oself: Any, value: TFunc) -> None:
        self._func = value
