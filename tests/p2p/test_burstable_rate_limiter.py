import asyncio
import pytest
import time

from p2p._utils import token_bucket


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
    assert delta < 0.0001


@pytest.mark.asyncio
async def test_token_bucket_hits_limit():
    limiter = token_bucket(1000, 10)

    start_at = time.perf_counter()
    # first 10 tokens should be roughly instant
    # next 10 tokens should each take 1/1000th second each to generate.
    for _ in range(20):
        await limiter.__anext__()

    end_at = time.perf_counter()

    expected_delta = 10 / 1000
    delta = end_at - start_at
    print('DELTA:', delta, expected_delta)

    # allow up to 10% drift from expected result
    assert abs(1 - (delta / expected_delta)) < 0.1


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
    assert delta < 0.0001
