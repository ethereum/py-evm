from __future__ import absolute_import

import rlp

from eth_utils import (
    to_tuple,
)


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
