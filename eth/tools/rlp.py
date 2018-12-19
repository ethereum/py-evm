from eth_utils import (
    replace_exceptions,
    ValidationError,
)

from eth._utils.rlp import (
    validate_rlp_equal,
)


assert_imported_genesis_header_unchanged = replace_exceptions({
    ValidationError: AssertionError,
})(validate_rlp_equal(obj_a_name='genesis header', obj_b_name='imported header'))


assert_mined_block_unchanged = replace_exceptions({
    ValidationError: AssertionError,
})(validate_rlp_equal(obj_a_name='block', obj_b_name='mined block'))


assert_headers_eq = replace_exceptions({
    ValidationError: AssertionError,
})(validate_rlp_equal(obj_a_name='expected', obj_b_name='actual'))
