from eth_utils import (
    ValidationError,
    replace_exceptions,
)

from eth._utils.rlp import (
    validate_rlp_equal,
)

assert_imported_block_unchanged = replace_exceptions(
    {
        ValidationError: AssertionError,
    }
)(validate_rlp_equal(obj_a_name="provided block", obj_b_name="executed block"))


assert_headers_eq = replace_exceptions(
    {
        ValidationError: AssertionError,
    }
)(validate_rlp_equal(obj_a_name="expected", obj_b_name="actual"))
