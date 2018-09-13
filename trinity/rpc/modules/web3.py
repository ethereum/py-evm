from eth_hash.auto import keccak
from eth_utils import decode_hex, encode_hex

from trinity.utils.version import construct_trinity_client_identifier

from trinity.rpc.modules import (
    RPCModule,
)


class Web3(RPCModule):
    async def clientVersion(self) -> str:
        """
        Returns the current client version.
        """
        return construct_trinity_client_identifier()

    async def sha3(self, data: str) -> str:
        """
        Returns Keccak-256 of the given data.
        """
        return encode_hex(keccak(decode_hex(data)))
