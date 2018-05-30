from eth_hash.auto import keccak
from eth_utils import decode_hex, encode_hex

from trinity.utils.version import construct_trinity_client_identifier

# Tell mypy to ignore this import as a workaround for https://github.com/python/mypy/issues/4049
from trinity.rpc.modules import (  # type: ignore
    RPCModule,
)


class Web3(RPCModule):
    def clientVersion(self):
        """
        Returns the current client version.
        """
        return construct_trinity_client_identifier()

    def sha3(self, data):
        """
        Returns Keccak-256 of the given data.
        """
        return encode_hex(keccak(decode_hex(data)))
