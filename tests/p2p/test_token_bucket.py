import asyncio
import pytest
import time

from p2p._utils import token_bucket


async def measure_zero(iterations):
    start_at = time.perf_counter()
    for _ in range(iterations):
        await asyncio.sleep(0)
    end_at = time.perf_counter()
    return end_at - start_at


def assert_fuzzy_equal(actual, expected, allowed_drift):
    assert abs(1 - (actual / expected)) < allowed_drift


@pytest.mark.asyncio
async def test_token_bucket_initial_tokens():
    limiter = token_bucket(1000, 10)

    start_at = time.perf_counter()
    for _ in range(10):
        await limiter.__anext__()

    end_at = time.perf_counter()
    delta = end_at - start_at

    # since the bucket starts out full the loop
    # should take near zero time
    expected = await measure_zero(10)
    # drift is allowed to be up to 200% since we're working with very small
    # numbers.
    assert_fuzzy_equal(delta, expected, allowed_drift=2)


@pytest.mark.asyncio
async def test_token_bucket_hits_limit():
    limiter = token_bucket(1000, 10)

    start_at = time.perf_counter()
    # first 10 tokens should be roughly instant
    # next 10 tokens should each take 1/1000th second each to generate.
    for _ in range(20):
        await limiter.__anext__()

    end_at = time.perf_counter()

    # we use a zero-measure of 20 to account for the loop overhead.
    expected_delta = 10 / 1000 + await measure_zero(20)
    delta = end_at - start_at

    # allow up to 1% difference in expected time
    assert_fuzzy_equal(delta, expected_delta, allowed_drift=0.01)


@pytest.mark.asyncio
async def test_token_bucket_refills_itself():
    limiter = token_bucket(1000, 10)

    # consume all of the tokens
    for _ in range(10):
        await limiter.__anext__()

    # enough time for the bucket to fully refill
    await asyncio.sleep(20 / 1000)

    start_at = time.perf_counter()

    for _ in range(10):
        await limiter.__anext__()

    end_at = time.perf_counter()

    delta = end_at - start_at
    # since the capacity should have been fully refilled, second loop time
    # should take near zero time
    expected = await measure_zero(10)
    # drift is allowed to be up to 200% since we're working with very small
    # numbers.
    assert_fuzzy_equal(delta, expected, allowed_drift=2)
