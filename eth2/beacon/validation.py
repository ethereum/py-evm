from typing import (
    Any,
)

from eth.validation import (
    validate_gte,
    validate_lte,
    validate_is_integer,
)


def validate_slot(slot: Any, title: str="Slot") -> None:
    validate_is_integer(slot, title)
    validate_gte(slot, 0, title)
    validate_lte(slot, 2**64 - 1, title)
