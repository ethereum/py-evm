# Some guidelines about development in the p2p module

The plan is for this to eventually become a comprehensive guide to aid when developing in the p2p
package, but for now it's just a collection of random notes/recommendations.


## Task cancellation

In order to make sure we stop all pending asyncio tasks upon exit (or when a service terminates),
we use `CancelToken`s, which are heavily inspired by https://vorpus.org/blog/timeouts-and-cancellation-for-humans/

- A `CancelToken` must be available to all our async APIs. Either as an instance attribute or as an explicit argument.
- When one of our async APIs `await` for stdlib/third-party coroutines, it must use `wait_with_token()` to ensure the scheduled task is cancelled when the token is triggered.


## BaseService

- If your service runs coroutines in the background (e.g. via `asyncio.ensure_future`), you must
  ensure they exit when `is_running` is False or when the cancel token is triggered
- If your service runs other services in the background, you should ensure your `_cleanup()` method stops them.
