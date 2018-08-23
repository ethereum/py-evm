# Some guidelines about development in the p2p module

The plan is for this to eventually become a comprehensive guide to aid when developing in the p2p
package, but for now it's just a collection of random notes/recommendations.


## Task cancellation

In order to make sure we stop all pending asyncio tasks upon exit (or when a service terminates),
we use `CancelToken`s from the
[asyncio-cancel-token](https://asyncio-cancel-token.readthedocs.io/en/latest/index.html)
library.

- A `CancelToken` must be available to all our async APIs. Either as an instance attribute or as an explicit argument.
- When one of our async APIs `await` for stdlib/third-party coroutines, it must use `CancelToken.cancellable_wait()` to ensure the scheduled task is cancelled when the token is triggered.


## BaseService

- If your service needs to run coroutines in the background, you should use the `BaseService.run_task()` method and
  ensure they exit when `is_operational` is False or when the cancel token is triggered.
- If your service runs other services in the background, you should pass your CancelToken down to
  those services and run those using `BaseService.run_child_service()`, or
  `BaseService.run_daemon()` if you want the parent to be terminated when the child dies
  unexpectedly.

```Python
class Node(BaseService):
    async def _run(self):
        self.discovery = DiscoveryService(token=self.cancel_token)
        self.run_daemon(self.discovery)
        self.run_task(self.discovery.bootstrap())
        # UPNP service is still experimental and not essential, so we don't use run_daemon() for
        # it as that means if it crashes we'd be terminated as well.
        self.run_child_service(UPnPService(token=self.cancel_token))
        # Node's run logic goes here...

```
