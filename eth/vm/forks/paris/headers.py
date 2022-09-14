from typing import Any, Callable, Optional

from toolz import curry

from eth.abc import BlockHeaderAPI
from eth.constants import (
    POST_MERGE_DIFFICULTY,
    POST_MERGE_MIX_HASH,
    POST_MERGE_NONCE,
)
from eth.vm.forks.gray_glacier.headers import (
    compute_gray_glacier_difficulty,
    create_gray_glacier_header_from_parent,
)
from eth.vm.forks.byzantium.headers import (
    configure_header,
)
from eth_utils import ValidationError
from .blocks import ParisBlockHeader


def _validate_and_return_paris_header_param(
    header_param: str,
    actual: Any,
    constant_value: Any,
) -> Any:
    if actual and actual != constant_value:
        raise ValidationError(
            f"Header param '{header_param}' must always be "
            f"{constant_value}, got: {actual}"
        )
    return constant_value


@curry
def create_paris_header_from_parent(
    _difficulty_fn: Callable[[BlockHeaderAPI, int], int],
    parent_header: Optional[BlockHeaderAPI],
    **header_params: Any,
) -> BlockHeaderAPI:
    if parent_header is None:
        if "mix_hash" not in header_params:
            header_params["mix_hash"] = POST_MERGE_MIX_HASH
        if "nonce" not in header_params:
            header_params["nonce"] = POST_MERGE_NONCE
        if "difficulty" not in header_params:
            header_params["difficulty"] = POST_MERGE_DIFFICULTY

    header_params["mix_hash"] = (
        header_params["mix_hash"] if "mix_hash" in header_params
        else parent_header.mix_hash
    )

    if parent_header is not None:
        if "difficulty" in header_params:
            header_params["difficulty"] = _validate_and_return_paris_header_param(
                "difficulty", header_params["difficulty"], POST_MERGE_DIFFICULTY
            )
        else:
            header_params["difficulty"] = POST_MERGE_DIFFICULTY

        if "nonce" in header_params:
            header_params["nonce"] = _validate_and_return_paris_header_param(
                "nonce", header_params["nonce"], POST_MERGE_NONCE
            )
        else:
            header_params["nonce"] = POST_MERGE_NONCE

    gray_glacier_validated_header = create_gray_glacier_header_from_parent(
        compute_gray_glacier_difficulty, parent_header, **header_params
    )

    # extract params validated up to gray glacier (previous VM)
    # and plug into a `ParisBlockHeader` class
    all_fields = gray_glacier_validated_header.as_dict()
    return ParisBlockHeader(**all_fields)


configure_paris_header = configure_header(POST_MERGE_DIFFICULTY)
