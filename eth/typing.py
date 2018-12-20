from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    NewType,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
    HexStr,
)
from mypy_extensions import (
    TypedDict,
)

if TYPE_CHECKING:
    from eth.rlp.transactions import BaseTransaction  # noqa: F401
    from eth.vm.spoof import SpoofTransaction  # noqa: F401
    from eth.vm.base import BaseVM  # noqa: F401


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

GenesisDict = Dict[str, Union[int, BlockNumber, bytes, Hash32]]

BytesOrView = Union[bytes, memoryview]

Normalizer = Callable[[Dict[Any, Any]], Dict[str, Any]]

RawAccountDetails = TypedDict('RawAccountDetails',
                              {'balance': HexStr,
                               'nonce': HexStr,
                               'code': HexStr,
                               'storage': Dict[HexStr, HexStr]
                               })

TransactionDict = TypedDict('TransactionDict',
                            {'nonce': int,
                             'gasLimit': int,
                             'gasPrice': int,
                             'to': Address,
                             'value': int,
                             'data': bytes,
                             'secretKey': bytes,
                             })

TransactionNormalizer = Callable[[TransactionDict], TransactionDict]

VMFork = Tuple[BlockNumber, Type['BaseVM']]

VMConfiguration = Sequence[VMFork]

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
