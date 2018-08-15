from trinity.protocol.common.validators import (
    BaseBlockHeadersValidator,
)
from . import constants


class GetBlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = constants.MAX_HEADERS_FETCH
