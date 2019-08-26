from eth_utils import ValidationError
import pytest

from eth2._utils.tuple import update_tuple_item


@pytest.mark.parametrize(
    ("tuple_data, index, new_value, expected"),
    [
        ((1,) * 10, 0, -99, (-99,) + (1,) * 9),
        ((1,) * 10, 5, -99, (1,) * 5 + (-99,) + (1,) * 4),
        ((1,) * 10, 9, -99, (1,) * 9 + (-99,)),
        ((1,) * 10, 10, -99, ValidationError()),
    ],
)
def test_update_tuple_item(tuple_data, index, new_value, expected):
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            update_tuple_item(tuple_data=tuple_data, index=index, new_value=new_value)
    else:
        result = update_tuple_item(
            tuple_data=tuple_data, index=index, new_value=new_value
        )
        assert result == expected
