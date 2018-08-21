from abc import ABC, abstractmethod
from typing import (
    Any,
    Generic,
    Tuple,
    TypeVar,
    cast,
)

from eth.rlp.headers import BlockHeader
from eth_typing import (
    BlockIdentifier,
    BlockNumber,
)
from eth_utils import (
    ValidationError,
    encode_hex,
)

from trinity.utils.headers import sequence_builder

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
            first_header = response[0]
            if first_header.hash != self.block_number_or_hash:
                raise ValidationError(
                    "Returned headers cannot be matched to header request. "
                    "Expected first header to have hash of {0} but instead got "
                    "{1}.".format(
                        encode_hex(self.block_number_or_hash),
                        encode_hex(first_header.hash),
                    )
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
                'Unexpected numbers: {0}'.format(unexpected_numbers))

        # check that the numbers are correctly ordered.
        expected_order = tuple(sorted(
            block_numbers,
            reverse=self.reverse,
        ))
        if block_numbers != expected_order:
            raise ValidationError(
                'Returned headers are not correctly ordered.\n'
                'Expected: {0}\n'
                'Got     : {1}\n'.format(expected_order, block_numbers)
            )

        # check that all provided numbers are an ordered subset of the master
        # sequence.
        iter_expected = iter(expected_numbers)
        for number in block_numbers:
            for value in iter_expected:
                if value == number:
                    break
            else:
                raise ValidationError(
                    'Returned headers contain an unexpected block number.\n'
                    'Unexpected Number: {0}\n'
                    'Expected Numbers : {1}'.format(number, expected_numbers)
                )
