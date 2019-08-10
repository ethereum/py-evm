"""
Tools for retrying failed RPC methods. If we're beam syncing we can fault in missing data
from remote peers.
"""
import itertools
from typing import (
    Any,
    Callable,
    TypeVar,
)

from lahja import EndpointAPI

from eth.vm.interrupt import (
    MissingAccountTrieNode,
)

from trinity.sync.common.events import (
    CollectMissingAccount,
)


Func = Callable[..., Any]
Meth = TypeVar('Meth', bound=Func)


RETRYABLE_ATTRIBUTE_NAME = '_is_rpc_retryable'
MAX_RETRIES = 1000


def retryable(func: Meth) -> Meth:
    setattr(func, RETRYABLE_ATTRIBUTE_NAME, True)
    return func


def is_retryable(func: Func) -> bool:
    return getattr(func, RETRYABLE_ATTRIBUTE_NAME, False)


def should_execute_with_retries(event_bus: EndpointAPI, func: Func) -> bool:
    return all((
        is_retryable(func),
        event_bus.is_any_endpoint_subscribed_to(CollectMissingAccount),
    ))


async def execute_with_retries(event_bus: EndpointAPI, func: Func, params: Any) -> None:
    """
    If a beam sync (or anything which responds to CollectMissingAccount) is running then
    attempt to fetch missing data from it before giving up.
    """
    should_retry = should_execute_with_retries(event_bus, func)

    for iteration in itertools.count():
        try:
            return await func(*params)
        except MissingAccountTrieNode as exc:
            if not should_retry:
                raise

            if iteration > MAX_RETRIES:
                raise Exception(
                    f"Failed to collect missing account after {MAX_RETRIES} attempts"
                ) from exc

            await event_bus.request(CollectMissingAccount(
                exc.missing_node_hash,
                exc.address_hash,
                exc.state_root_hash,
                urgent=True,
            ))
