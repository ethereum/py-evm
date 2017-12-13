from evm.rpc.format import (
    format_params,
)

from evm.rpc.modules import (
    RPCModule,
)

from evm.utils.fixture_tests import (
    apply_fixture_blocks_to_chain,
    new_chain_from_fixture,
    normalize_blockchain_fixtures,
)


class Debug(RPCModule):
    @format_params(normalize_blockchain_fixtures)
    def resetChainTo(self, chain_info):
        '''
        This method is a special case. It returns a new chain object
        which is then replaced inside :class:`~evm.rpc.main.RPCServer`
        for all future calls.
        '''
        chain = new_chain_from_fixture(chain_info)
        apply_fixture_blocks_to_chain(chain_info['blocks'], chain)
        return chain
