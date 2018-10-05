from eth.validation import (
    validate_gte,
    validate_lte,
    validate_is_integer,
)


def validate_slot(slot):
    validate_is_integer(slot, title="Slot")
    validate_gte(slot, 0, title="Slot")
    validate_lte(slot, 2**64 - 1, title="Slot")
