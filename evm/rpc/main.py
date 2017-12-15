import json
import logging

from evm.exceptions import (
    ValidationError,
)

from evm.rpc.modules import (
    Eth,
    EVM,
)


def generate_response(request):
    return {
        'id': request['id'],
        'jsonrpc': request['jsonrpc'],
    }


class RPCServer:
    '''
    This "server" accepts json strings requests and returns the appropriate json string response,
    meeting the protocol for JSON-RPC defined here: https://github.com/ethereum/wiki/wiki/JSON-RPC

    The key entry point for all requests is :meth:`RPCServer.request`, which
    then proxies to the appropriate method. For example, see
    :meth:`RPCServer.eth_getBlockByHash`.
    '''

    module_classes = (
        Eth,
        EVM,
    )

    def __init__(self, chain):
        self.modules = {}
        self.chain = chain
        for M in self.module_classes:
            self.modules[M.__name__.lower()] = M(chain)

    def _lookup_method(self, rpc_method):
        method_pieces = rpc_method.split('_')

        if len(method_pieces) != 2:
            # This check provides a security guarantee: that it's impossible to invoke
            # a method with an underscore in it. Only public methods on the modules
            # will be callable by external clients.
            raise ValueError("Invalid RPC method: %r" % rpc_method)
        module_name, method_name = method_pieces

        if module_name not in self.modules:
            raise ValueError("Module unavailable: %r" % module_name)
        module = self.modules[module_name]

        try:
            return getattr(module, method_name)
        except AttributeError:
            raise ValueError("Method not implemented: %r" % rpc_method)

    def execute(self, request):
        '''
        The key entry point for all incoming requests
        '''
        response = generate_response(request)

        try:
            if request.get('jsonrpc', None) != '2.0':
                raise NotImplementedError("Only the 2.0 jsonrpc protocol is supported")

            method = self._lookup_method(request['method'])
            params = request.get('params', [])
            response['result'] = method(*params)
        except NotImplementedError as exc:
            response['error'] = "Method not implemented: %r" % request['method']
            custom_message = str(exc)
            if custom_message:
                response['error'] += ' - %s' % custom_message
        except ValidationError as exc:
            logging.debug("Validation error while executing RPC method", exc_info=True)
            response['error'] = str(exc)
        except Exception as exc:
            logging.info("RPC method caused exception", exc_info=True)
            response['error'] = str(exc)

        if request['method'] == 'evm_resetToGenesisFixture' and 'result' in response:
            self.chain = response['result']
            response['result'] = True

        return json.dumps(response)

    @property
    def chain(self):
        return self.__chain

    @chain.setter
    def chain(self, new_chain):
        self.__chain = new_chain
        for module in self.modules.values():
            module.chain = new_chain
