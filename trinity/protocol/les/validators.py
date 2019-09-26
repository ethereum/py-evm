from typing import Any

from eth_utils import (
    ValidationError,
)

from trinity.protocol.common.validators import (
    BaseBlockHeadersValidator,
)
from . import constants


class GetBlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = constants.MAX_HEADERS_FETCH


def match_payload_request_id(request: Any, response: Any) -> None:
    if request.request_id != response.payload.request_id:
        raise ValidationError("Request `id` does not match")
