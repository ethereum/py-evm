import json
import logging
from typing import (
    Any,
    Dict,
    Sequence,
    Tuple,
    Union,
)

from eth_utils import (
    ValidationError,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.rpc.modules import (
    BaseRPCModule,
)

REQUIRED_REQUEST_KEYS = {
    'id',
    'jsonrpc',
    'method',
}


def validate_request(request: Dict[str, Any]) -> None:
    missing_keys = REQUIRED_REQUEST_KEYS - set(request.keys())
    if missing_keys:
        raise ValueError("request must include the keys: %r" % missing_keys)


def generate_response(request: Dict[str, Any], result: Any, error: Union[Exception, str]) -> str:
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
    """
    This "server" accepts json strings requests and returns the appropriate json string response,
    meeting the protocol for JSON-RPC defined here: https://github.com/ethereum/wiki/wiki/JSON-RPC

    The key entry point for all requests is :meth:`RPCServer.request`, which
    then proxies to the appropriate method. For example, see
    :meth:`RPCServer.eth_getBlockByHash`.
    """
    chain = None

    def __init__(self,
                 modules: Sequence[BaseRPCModule],
                 event_bus: TrinityEventBusEndpoint=None) -> None:
        self.modules: Dict[str, BaseRPCModule] = {}

        for module in modules:
            name = module.name.lower()

            if name in self.modules:
                raise ValueError(
                    f"Apparent name conflict in registered RPC modules, {name} already registered"
                )

            self.modules[name] = module

    def _lookup_method(self, rpc_method: str) -> Any:
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

    async def _get_result(self,
                          request: Dict[str, Any],
                          debug: bool=False) -> Tuple[Any, Union[Exception, str]]:
        """
        :returns: (result, error) - result is None if error is provided. Error must be
            convertable to string with ``str(error)``.
        """
        try:
            validate_request(request)

            if request.get('jsonrpc', None) != '2.0':
                raise NotImplementedError("Only the 2.0 jsonrpc protocol is supported")

            method = self._lookup_method(request['method'])
            params = request.get('params', [])
            result = await method(*params)

            if request['method'] == 'evm_resetToGenesisFixture':
                result = True

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

    async def execute(self, request: Dict[str, Any]) -> str:
        """
        The key entry point for all incoming requests
        """
        result, error = await self._get_result(request)
        return generate_response(request, result, error)
