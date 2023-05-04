from typing import (
    Iterable,
    Optional,
    Tuple,
)

from eth_utils import (
    ValidationError,
    to_tuple,
)
from eth_utils.toolz import (
    curry,
)
import rlp

from eth.rlp.blocks import (
    BaseBlock,
)


@to_tuple
def diff_rlp_object(
    left: BaseBlock, right: BaseBlock
) -> Optional[Iterable[Tuple[str, str, str]]]:
    if left != right:
        rlp_type = type(left)

        for field_name, field_type in rlp_type._meta.fields:
            left_value = getattr(left, field_name)
            right_value = getattr(right, field_name)
            if isinstance(field_type, type) and issubclass(
                field_type, rlp.Serializable
            ):
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


def _humanized_diff_elements(
    diff: Iterable[Tuple[str, str, str]], obj_a_name: str, obj_b_name: str
) -> Iterable[str]:
    longest_obj_name = max(len(obj_a_name), len(obj_b_name))

    for field_name, a_val, b_val in diff:
        if isinstance(a_val, int) and isinstance(b_val, int):
            element_diff = b_val - a_val
            if element_diff > 0:
                element_diff_display = f" (+{element_diff})"
            else:
                element_diff_display = f" ({element_diff})"
        else:
            element_diff_display = ""

        yield (
            f"{field_name}:\n"
            f"    ({obj_a_name.ljust(longest_obj_name, ' ')}) : {a_val}\n"
            f"    ({obj_b_name.ljust(longest_obj_name, ' ')}) : {b_val}{element_diff_display}"  # noqa: E501
        )


@curry
def validate_rlp_equal(
    obj_a: BaseBlock, obj_b: BaseBlock, obj_a_name: str = None, obj_b_name: str = None
) -> None:
    if obj_a == obj_b:
        return

    if obj_a_name is None:
        obj_a_name = obj_a.__class__.__name__ + "_a"
    if obj_b_name is None:
        obj_b_name = obj_b.__class__.__name__ + "_b"

    diff = diff_rlp_object(obj_a, obj_b)
    if len(diff) == 0:
        raise TypeError(
            f"{obj_a_name} ({obj_a!r}) != "
            f"{obj_b_name} ({obj_b!r}) but got an empty diff"
        )

    err_fields = "\n - ".join(_humanized_diff_elements(diff, obj_a_name, obj_b_name))
    error_message = (
        f"Mismatch between {obj_a_name} and {obj_b_name} "
        f"on {len(diff)} fields:\n - {err_fields}"
    )
    raise ValidationError(error_message)


validate_imported_block_unchanged = validate_rlp_equal(
    obj_a_name="locally executed block",
    obj_b_name="proposed block",
)
