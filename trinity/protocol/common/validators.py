from abc import ABC, abstractmethod
import collections
from typing import (
    Any,
    Generic,
    Tuple,
    TypeVar,
    cast,
)

from eth.rlp.headers import BlockHeader
from eth_typing import (
    Hash32,
    BlockIdentifier,
    BlockNumber,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    humanize_hash,
)

from trinity._utils.headers import sequence_builder
from trinity._utils.humanize import humanize_integer_sequence

TResponse = TypeVar('TResponse')


def noop_payload_validator(request: Any, response: Any) -> None:
    pass


class BaseValidator(ABC, Generic[TResponse]):
    """
    A validator which compares the initial request to its normalized result.
    """
    @abstractmethod
    def validate_result(self, result: TResponse) -> None:
        pass


class BaseBlockHeadersValidator(BaseValidator[Tuple[BlockHeader, ...]]):
    block_number_or_hash: BlockIdentifier
    max_headers: int
    skip: int
    reverse: bool

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool) -> None:
        self.block_number_or_hash = block_number_or_hash
        self.max_headers = max_headers
        self.skip = skip
        self.reverse = reverse

    @property
    @abstractmethod
    def protocol_max_request_size(self) -> int:
        raise NotImplementedError

    def validate_result(self, response: Tuple[BlockHeader, ...]) -> None:
        if not response:
            # An empty response is always valid
            return
        elif not self._is_numbered:
            block_hash = cast(Hash32, self.block_number_or_hash)
            first_header = response[0]
            if first_header.hash != block_hash:
                raise ValidationError(
                    "Returned headers cannot be matched to header request. "
                    "Expected first header to have hash of "
                    f"{encode_hex(block_hash)} but instead got "
                    f"{encode_hex(first_header.hash)}. "
                    f'Requested: {self._get_formatted_params()}'
                )

        block_numbers: Tuple[BlockNumber, ...] = tuple(
            header.block_number for header in response
        )
        return self._validate_sequence(block_numbers)

    def _generate_block_numbers(self, block_number: BlockNumber=None) -> Tuple[BlockNumber, ...]:
        if block_number is None and not self._is_numbered:
            raise TypeError(
                "A `block_number` must be supplied to generate block numbers "
                "for hash based header requests"
            )
        elif block_number is not None and self._is_numbered:
            raise TypeError(
                "The `block_number` parameter may not be used for number based "
                "header requests"
            )
        elif block_number is None:
            block_number = cast(BlockNumber, self.block_number_or_hash)

        max_headers = min(self.protocol_max_request_size, self.max_headers)

        return sequence_builder(
            block_number,
            max_headers,
            self.skip,
            self.reverse,
        )

    @property
    def _is_numbered(self) -> bool:
        return isinstance(self.block_number_or_hash, int)

    @property
    def block_identifier(self) -> str:
        if isinstance(self.block_number_or_hash, int):
            return str(self.block_number_or_hash)
        elif isinstance(self.block_number_or_hash, bytes):
            return humanize_hash(self.block_number_or_hash)
        else:
            raise Exception(
                f"Unexpected type for block identifier: "
                f"{type(self.block_number_or_hash)}"
            )

    def _get_formatted_params(self) -> str:
        return (
            f'ident: {self.block_identifier}  '
            f'max={self.max_headers}  '
            f'skip={self.skip}  '
            f'reverse={self.reverse}'
        )

    def _validate_sequence(self, block_numbers: Tuple[BlockNumber, ...]) -> None:
        if not block_numbers:
            return
        elif self._is_numbered:
            expected_numbers = self._generate_block_numbers()
        else:
            expected_numbers = self._generate_block_numbers(block_numbers[0])

        # check for numbers that should not be present.
        unexpected_numbers = set(block_numbers).difference(expected_numbers)
        if unexpected_numbers:
            raise ValidationError(
                f'Got unexpected headers:\n'
                f' - request params: {self._get_formatted_params()}\n'
                f' - unexpected: {humanize_integer_sequence(sorted(unexpected_numbers))}\n'
                f' - expected  : {humanize_integer_sequence(expected_numbers)}\n'
            )

        # check that the numbers are correctly ordered.
        expected_order = tuple(sorted(
            block_numbers,
            reverse=self.reverse,
        ))
        if block_numbers != expected_order:
            raise ValidationError(
                'Headers are incorrectly ordered.\n'
                f'- expected: {humanize_integer_sequence(expected_order)}\n'
                f'- actual  : {block_numbers}\n'
            )

        # check that there are no duplicate numbers
        duplicates = {
            key for
            key, value in
            collections.Counter(block_numbers).items()
            if value > 1
        }
        if duplicates:
            raise ValidationError(
                'Duplicate headers returned.\n'
                f'- duplicates: {humanize_integer_sequence(sorted(duplicates))}\n'
            )
