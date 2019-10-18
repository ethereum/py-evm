import rlp
from typing import (
    Iterable,
    Optional,
    Tuple,
)

from eth_utils.toolz import (
    curry,
)

from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.rlp.blocks import (
    BaseBlock,
)


@to_tuple
def diff_rlp_object(left: BaseBlock,
                    right: BaseBlock) -> Optional[Iterable[Tuple[str, str, str]]]:
    if left != right:
        rlp_type = type(left)

        for field_name, field_type in rlp_type._meta.fields:
            left_value = getattr(left, field_name)
            right_value = getattr(right, field_name)
            if isinstance(field_type, type) and issubclass(field_type, rlp.Serializable):
                sub_diff = diff_rlp_object(left_value, right_value)
                for sub_field_name, sub_left_value, sub_right_value in sub_diff:
                    yield (
                        f"{field_name}.{sub_field_name}",
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
def validate_rlp_equal(obj_a: BaseBlock,
                       obj_b: BaseBlock,
                       obj_a_name: str=None,
                       obj_b_name: str=None) -> None:
    if obj_a == obj_b:
        return

    if obj_a_name is None:
        obj_a_name = obj_a.__class__.__name__ + '_a'
    if obj_b_name is None:
        obj_b_name = obj_b.__class__.__name__ + '_b'

    diff = diff_rlp_object(obj_a, obj_b)
    if len(diff) == 0:
        raise TypeError(
            f"{obj_a_name} ({obj_a!r}) != "
            f"{obj_b_name} ({obj_b!r}) but got an empty diff"
        )
    longest_field_name = max(len(field_name) for field_name, _, _ in diff)

    err_fields = "\n - ".join(
        tuple(
            f"{field_name.ljust(longest_field_name, ' ')}:\n"
            f"    (actual)  : {actual}\n    (expected): {expected}"
            for field_name, actual, expected
            in diff
        )
    )
    error_message = (
        f"Mismatch between {obj_a_name} and {obj_b_name} "
        f"on {len(diff)} fields:\n - {err_fields}"
    )
    raise ValidationError(error_message)


validate_imported_block_unchanged = validate_rlp_equal(
    obj_a_name="block",
    obj_b_name="imported block",
)
