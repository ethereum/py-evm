from eth_utils import (
    encode_hex,
)

from evm.tools.fixture_tests import (
    apply_fixture_block_to_chain,
    new_chain_from_fixture,
    normalize_block,
    normalize_blockchain_fixtures,
)

from trinity.rpc.format import (
    format_params,
)
# Tell mypy to ignore this import as a workaround for https://github.com/python/mypy/issues/4049
from trinity.rpc.modules import (  # type: ignore
    RPCModule,
)


class EVM(RPCModule):
    @format_params(normalize_blockchain_fixtures)
    def resetToGenesisFixture(self, chain_info):
        '''
        This method is a special case. It returns a new chain object
        which is then replaced inside :class:`~trinity.rpc.main.RPCServer`
        for all future calls.
        '''
        return new_chain_from_fixture(chain_info)

    @format_params(normalize_block)
    def applyBlockFixture(self, block_info):
        '''
        This method is a special case. It returns a new chain object
        which is then replaced inside :class:`~trinity.rpc.main.RPCServer`
        for all future calls.
        '''
        _, _, rlp_encoded = apply_fixture_block_to_chain(block_info, self._chain)
        return encode_hex(rlp_encoded)
