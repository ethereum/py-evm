# Some guidelines about development in the p2p module

The plan is for this to eventually become a comprehensive guide to aid when developing in the p2p
package, but for now it's just a collection of random notes/recommendations.


## Task cancellation

In order to make sure we stop all pending asyncio tasks upon exit (or when a service terminates),
we use `CancelToken`s, which are heavily inspired by https://vorpus.org/blog/timeouts-and-cancellation-for-humans/

- A `CancelToken` must be available to all our async APIs. Either as an instance attribute or as an explicit argument.
- When one of our async APIs `await` for stdlib/third-party coroutines, it must use `wait_with_token()` to ensure the scheduled task is cancelled when the token is triggered.
- We must never use `wait_with_token()` with coroutines that create other tasks as when the token is triggered and the coroutine passed to `wait_with_token()` is cancelled, the tasks created by it are automatically destroyed by the event loop and we'll get ERROR logs if those tasks were still pending.


## BaseService

- If your service runs coroutines in the background (e.g. via `asyncio.ensure_future`), you must
  ensure they exit when `is_finished` is True or when the cancel token is triggered
- If your service runs other services in the background, you should ensure your `_cleanup()` method stops them.
