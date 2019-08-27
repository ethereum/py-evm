"""
Tools for retrying failed RPC methods. If we're beam syncing we can fault in missing data
from remote peers.
"""
import inspect
import itertools
from typing import (
    Any,
    Callable,
    Optional,
    TypeVar,
)

from lahja import EndpointAPI

from eth.vm.interrupt import (
    MissingAccountTrieNode,
    MissingBytecode,
    MissingStorageTrieNode,
)

from trinity.chains.base import AsyncChainAPI
from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
)

from trinity.rpc.modules._util import get_header


Func = Callable[..., Any]
Meth = TypeVar('Meth', bound=Func)


RETRYABLE_ATTRIBUTE_NAME = '_is_rpc_retryable'
AT_BLOCK_ATTRIBUTE_NAME = '_at_block_parameter'
MAX_RETRIES = 1000


def retryable(which_block_arg_name: str) -> Func:
    """
    A decorator which marks eth_* RPCs which:
    - are idempotent
    - throw errors which the beam syncer can help to recover from

    :param which_block_arg_name: names one of the arguments of the wrapped function.
    Specifically, the arg used to pass in the block identifier ("at_block", usually)
    """
    def make_meth_retryable(meth: Meth) -> Meth:
        sig = inspect.signature(meth)
        if which_block_arg_name not in sig.parameters:
            raise Exception(
                f'"{which_block_arg_name}" does not name an argument to this function'
            )

        setattr(meth, RETRYABLE_ATTRIBUTE_NAME, True)
        setattr(meth, AT_BLOCK_ATTRIBUTE_NAME, which_block_arg_name)
        return meth
    return make_meth_retryable


def is_retryable(func: Func) -> bool:
    return getattr(func, RETRYABLE_ATTRIBUTE_NAME, False)


async def check_requested_block_age(chain: Optional[AsyncChainAPI],
                                    func: Func, params: Any) -> None:
    sig = inspect.signature(func)
    params = sig.bind(*params)

    try:
        at_block_name = getattr(func, AT_BLOCK_ATTRIBUTE_NAME)
    except AttributeError as e:
        raise Exception("Function {func} was not decorated with @retryable") from e

    at_block = params.arguments[at_block_name]

    requested_header = await get_header(chain, at_block)
    requested_block = requested_header.block_number
    current_block = chain.get_canonical_head().block_number

    if requested_block < current_block - 64:
        raise Exception(f'block "{at_block}" is too old to be fetched over the network')


async def execute_with_retries(event_bus: EndpointAPI, func: Func, params: Any,
                               chain: Optional[AsyncChainAPI]) -> None:
    """
    If a beam sync (or anything which responds to CollectMissingAccount) is running then
    attempt to fetch missing data from it before giving up.
    """
    retryable = is_retryable(func)

    for iteration in itertools.count():
        try:
            return await func(*params)
        except MissingAccountTrieNode as exc:
            if not retryable:
                raise

            if iteration > MAX_RETRIES:
                raise Exception(
                    f"Failed to collect all necessary state after {MAX_RETRIES} attempts"
                ) from exc

            if not event_bus.is_any_endpoint_subscribed_to(CollectMissingAccount):
                raise

            await check_requested_block_age(chain, func, params)

            await event_bus.request(CollectMissingAccount(
                exc.missing_node_hash,
                exc.address_hash,
                exc.state_root_hash,
                urgent=True,
            ))
        except MissingBytecode as exc:
            if not retryable:
                raise

            if iteration > MAX_RETRIES:
                raise Exception(
                    f"Failed to collect all necessary state after {MAX_RETRIES} attempts"
                ) from exc

            if not event_bus.is_any_endpoint_subscribed_to(CollectMissingBytecode):
                raise

            await check_requested_block_age(chain, func, params)

            await event_bus.request(CollectMissingBytecode(
                bytecode_hash=exc.missing_code_hash,
                urgent=True,
            ))
        except MissingStorageTrieNode as exc:
            if not retryable:
                raise

            if iteration > MAX_RETRIES:
                raise Exception(
                    f"Failed to collect all necessary state after {MAX_RETRIES} attempts"
                ) from exc

            if not event_bus.is_any_endpoint_subscribed_to(CollectMissingStorage):
                raise

            await check_requested_block_age(chain, func, params)

            await event_bus.request(CollectMissingStorage(
                missing_node_hash=exc.missing_node_hash,
                storage_key=exc.requested_key,
                storage_root_hash=exc.storage_root_hash,
                account_address=exc.account_address,
                urgent=True,
            ))
