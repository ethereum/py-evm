from typing import (
    List,
    TYPE_CHECKING,
)

from eth_utils import (
    to_tuple,
)

if TYPE_CHECKING:
    from eth.beacon.types.validator_record import ValidatorRecord  # noqa: F401


@to_tuple
def get_active_validator_indices(dynasty: int,
                                 validators: List['ValidatorRecord']) -> List[int]:
    o = []
    for index, validator in enumerate(validators):
        if (validator.start_dynasty <= dynasty and dynasty < validator.end_dynasty):
            o.append(index)
    return o
