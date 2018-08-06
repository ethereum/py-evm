from abc import ABC, abstractmethod
from typing import (
    Any,
    cast,
    Tuple,
)

from eth_utils import encode_hex

from eth_typing import BlockIdentifier, BlockNumber

from eth.rlp.headers import BlockHeader

from p2p.exceptions import (
    ValidationError,
)


class BaseRequest(ABC):
    """
    Base representation of a *request* to a connected peer which has a matching
    *response*.
    """
    @abstractmethod
    def validate_response(self, response: Any) -> None:
        pass


class BaseHeaderRequest(BaseRequest):
    block_number_or_hash: BlockIdentifier
    max_headers: int
    skip: int
    reverse: bool

    @property
    @abstractmethod
    def max_size(self) -> int:
        pass

    def generate_block_numbers(self,
                               block_number: BlockNumber=None) -> Tuple[BlockNumber, ...]:
        if block_number is None and not self.is_numbered:
            raise TypeError(
                "A `block_number` must be supplied to generate block numbers "
                "for hash based header requests"
            )
        elif block_number is not None and self.is_numbered:
            raise TypeError(
                "The `block_number` parameter may not be used for number based "
                "header requests"
            )
        elif block_number is None:
            block_number = cast(BlockNumber, self.block_number_or_hash)

        max_headers = min(self.max_size, self.max_headers)

        # inline import until this module is moved to `trinity`
        from trinity.utils.headers import sequence_builder
        return sequence_builder(
            block_number,
            max_headers,
            self.skip,
            self.reverse,
        )

    @property
    def is_numbered(self) -> bool:
        return isinstance(self.block_number_or_hash, int)

    def validate_headers(self,
                         headers: Tuple[BlockHeader, ...]) -> None:
        if not headers:
            # An empty response is always valid
            return
        elif not self.is_numbered:
            first_header = headers[0]
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
            header.block_number for header in headers
        )
        return self.validate_sequence(block_numbers)

    def validate_sequence(self, block_numbers: Tuple[BlockNumber, ...]) -> None:
        if not block_numbers:
            return
        elif self.is_numbered:
            expected_numbers = self.generate_block_numbers()
        else:
            expected_numbers = self.generate_block_numbers(block_numbers[0])

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
