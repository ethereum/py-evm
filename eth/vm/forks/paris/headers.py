from typing import (
    Any,
    Optional,
)

from eth_utils import (
    ValidationError,
)
from toolz import (
    curry,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.constants import (
    POST_MERGE_DIFFICULTY,
    POST_MERGE_MIX_HASH,
    POST_MERGE_NONCE,
)
from eth.vm.forks.byzantium.headers import (
    configure_header,
)
from eth.vm.forks.gray_glacier.headers import (
    compute_gray_glacier_difficulty,
    create_gray_glacier_header_from_parent,
)

from .blocks import (
    ParisBlockHeader,
)


def _validate_and_return_paris_header_param(
    header_param: str,
    actual: Any,
    constant_value: Any,
) -> Any:
    # if a value is passed into `header_params`, validate it's correct; else, set to
    # the defined EIP-3675 constant value for the `header_param`.
    if actual is not None and actual != constant_value:
        raise ValidationError(
            f"Header param '{header_param}' must always be "
            f"{constant_value}, got: {actual}"
        )
    return constant_value


@curry
def create_paris_header_from_parent(
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    # `mix_hash` is not strictly validated; take the value from the `header_params`,
    # if present; else, set to the EIP-3675-defined constant value.
    header_params["mix_hash"] = header_params.get("mix_hash", POST_MERGE_MIX_HASH)

    # for `difficulty` and `nonce`, if present in `header_params`, validate the value
    # is the expected EIP-3675 value; else, set to the EIP-3675-defined constant value.
    header_params["difficulty"] = _validate_and_return_paris_header_param(
        "difficulty", header_params.get("difficulty"), POST_MERGE_DIFFICULTY
    )
    header_params["nonce"] = _validate_and_return_paris_header_param(
        "nonce", header_params.get("nonce"), POST_MERGE_NONCE
    )

    gray_glacier_validated_header = create_gray_glacier_header_from_parent(
        compute_gray_glacier_difficulty, parent_header, **header_params
    )

    # extract params validated up to gray glacier (previous VM)
    # and plug into a `ParisBlockHeader` class
    all_fields = gray_glacier_validated_header.as_dict()
    return ParisBlockHeader(**all_fields)


configure_paris_header = configure_header()
