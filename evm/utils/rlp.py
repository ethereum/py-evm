from __future__ import absolute_import

import rlp

from cytoolz import (
    curry,
)

from eth_utils import (
    to_tuple,
)

from evm.exceptions import ValidationError


@to_tuple
def diff_rlp_object(left, right):
    if left != right:
        rlp_type = type(left)

        for field_name, field_type in rlp_type.fields:
            left_value = getattr(left, field_name)
            right_value = getattr(right, field_name)
            if isinstance(field_type, type) and issubclass(field_type, rlp.Serializable):
                sub_diff = diff_rlp_object(left_value, right_value)
                for sub_field_name, sub_left_value, sub_right_value in sub_diff:
                    yield (
                        "{0}.{1}".format(field_name, sub_field_name),
                        sub_left_value,
                        sub_right_value,
                    )
            elif isinstance(field_type, (rlp.sedes.List, rlp.sedes.CountableList)):
                if tuple(left_value) != tuple(right_value):
                    yield (
                        field_name,
                        left_value,
                        right_value,
                    )
            elif left_value != right_value:
                yield (
                    field_name,
                    left_value,
                    right_value,
                )
            else:
                continue


@curry
def ensure_rlp_objects_are_equal(obj_a, obj_b, obj_a_name, obj_b_name):
    if obj_a == obj_b:
        return
    diff = diff_rlp_object(obj_a, obj_b)
    longest_field_name = max(len(field_name) for field_name, _, _ in diff)
    error_message = (
        "Mismatch between {obj_a_name} and {obj_b_name} on {0} fields:\n - {1}".format(
            len(diff),
            "\n - ".join(tuple(
                "{0}:\n    (actual)  : {1}\n    (expected): {2}".format(
                    field_name.ljust(longest_field_name, ' '),
                    actual,
                    expected,
                )
                for field_name, actual, expected
                in diff
            )),
            obj_a_name=obj_a_name,
            obj_b_name=obj_b_name,
        )
    )
    raise ValidationError(error_message)


ensure_imported_block_unchanged = ensure_rlp_objects_are_equal(
    obj_a_name="block",
    obj_b_name="imported block",
)
