import json
import logging
from typing import Dict  # noqa: F401

from evm.exceptions import (
    ValidationError,
)

from trinity.rpc.modules import (  # noqa: F401
    Eth,
    EVM,
    RPCModule,
)

REQUIRED_REQUEST_KEYS = {
    'id',
    'jsonrpc',
    'method',
}


def validate_request(request):
    missing_keys = REQUIRED_REQUEST_KEYS - set(request.keys())
    if missing_keys:
        raise ValueError("request must include the keys: %r" % missing_keys)


def generate_response(request, result, error):
    response = {
        'id': request.get('id', -1),
        'jsonrpc': request.get('jsonrpc', "2.0"),
    }

    if error is None:
        response['result'] = result
    elif result is not None:
        raise ValueError("Must not supply both a result and an error for JSON-RPC response")
    else:
        # only error is not None
        response['error'] = str(error)

    return json.dumps(response)


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
        self.modules = {}  # type: Dict[str, RPCModule]
        self.chain = chain
        for M in self.module_classes:
            self.modules[M.__name__.lower()] = M(chain)
        if len(self.modules) != len(self.module_classes):
            raise ValueError("apparent name conflict in RPC module_classes", self.module_classes)

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

    def _get_result(self, request, debug=False):
        '''
        :returns: (result, error) - result is None if error is provided. Error must be
            convertable to string with ``str(error)``.
        '''
        try:
            validate_request(request)

            if request.get('jsonrpc', None) != '2.0':
                raise NotImplementedError("Only the 2.0 jsonrpc protocol is supported")

            method = self._lookup_method(request['method'])
            params = request.get('params', [])
            result = method(*params)

            if request['method'] == 'evm_resetToGenesisFixture':
                self.chain, result = result, True

        except NotImplementedError as exc:
            error = "Method not implemented: %r %s" % (request['method'], exc)
            return None, error
        except ValidationError as exc:
            logging.debug("Validation error while executing RPC method", exc_info=True)
            return None, exc
        except Exception as exc:
            logging.info("RPC method caused exception", exc_info=True)
            if debug:
                raise Exception("failure during rpc call with %s" % request) from exc
            return None, exc
        else:
            return result, None

    def execute(self, request):
        '''
        The key entry point for all incoming requests
        '''
        result, error = self._get_result(request)
        return generate_response(request, result, error)

    @property
    def chain(self):
        return self.__chain

    @chain.setter
    def chain(self, new_chain):
        self.__chain = new_chain
        for module in self.modules.values():
            module.chain = new_chain
