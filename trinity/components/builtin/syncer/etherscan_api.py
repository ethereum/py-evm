from typing import (
    Any,
    Dict,
)
from eth_utils import (
    to_hex,
    to_int,
)

import requests

from trinity.exceptions import BaseTrinityError


ETHERSCAN_API_URL = "https://api.etherscan.io/api"
ETHERSCAN_PROXY_API_URL = f"{ETHERSCAN_API_URL}?module=proxy"


class EtherscanAPIError(BaseTrinityError):
    pass


def etherscan_post(action: str) -> Any:
    response = requests.post(f"{ETHERSCAN_PROXY_API_URL}&action={action}")

    if response.status_code not in [200, 201]:
        raise EtherscanAPIError(
            f"Invalid status code: {response.status_code}, {response.reason}"
        )

    try:
        value = response.json()
    except ValueError as err:
        raise EtherscanAPIError(f"Invalid response: {response.text}") from err

    message = value.get('message', '')
    result = value['result']

    api_error = message == 'NOTOK' or result == 'Error!'

    if api_error:
        raise EtherscanAPIError(f"API error: {message}, result: {result}")

    return value['result']


def get_latest_block() -> int:
    response = etherscan_post("eth_blockNumber")
    return to_int(hexstr=response)


def get_block_by_number(block_number: int) -> Dict[str, Any]:
    num = to_hex(primitive=block_number)
    return etherscan_post(f"eth_getBlockByNumber&tag={num}&boolean=false")
