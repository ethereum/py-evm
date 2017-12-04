from eth_utils import (
    decode_hex,
)

from evm.rpc.format import (
    block_to_dict,
)
from evm.rpc.modules import (
    RPCModule,
)


class Eth(RPCModule):
    '''
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    '''

    def getBlockByHash(self, block_hash_hex, include_transactions):
        block_hash = decode_hex(block_hash_hex)
        block = self._chain.get_block_by_hash(block_hash)
        assert block.hash == block_hash

        block_dict = block_to_dict(block, self._chain, include_transactions)

        return block_dict
