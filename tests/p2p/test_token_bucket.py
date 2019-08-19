import asyncio
import pytest
import time

from p2p.token_bucket import (
    TokenBucket,
    NotEnoughTokens,
)


async def measure_zero(iterations):
    bucket = TokenBucket(1, iterations)
    start_at = time.perf_counter()
    for _ in range(iterations):
        await bucket.take()
    end_at = time.perf_counter()
    return end_at - start_at


def assert_fuzzy_equal(actual, expected, allowed_drift):
    assert abs(1 - (actual / expected)) < allowed_drift


@pytest.mark.asyncio
async def test_token_bucket_initial_tokens():
    bucket = TokenBucket(1000, 10)

    start_at = time.perf_counter()
    for _ in range(10):
        await bucket.take()

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
    bucket = TokenBucket(1000, 10)

    bucket.take_nowait(10)
    start_at = time.perf_counter()
    # first 10 tokens should be roughly instant
    # next 10 tokens should each take 1/1000th second each to generate.
    while True:
        if bucket.can_take(10):
            break
        else:
            await asyncio.sleep(0)

    end_at = time.perf_counter()

    # we use a zero-measure of 20 to account for the loop overhead.
    zero = await measure_zero(10)
    expected_delta = 10 / 1000 + zero
    delta = end_at - start_at

    # allow up to 10% difference in expected time
    assert_fuzzy_equal(delta, expected_delta, allowed_drift=0.1)


@pytest.mark.asyncio
async def test_token_bucket_refills_itself():
    bucket = TokenBucket(1000, 10)

    # consume all of the tokens
    for _ in range(10):
        await bucket.take()

    # enough time for the bucket to fully refill
    await asyncio.sleep(20 / 1000)

    start_at = time.perf_counter()

    for _ in range(10):
        await bucket.take()

    end_at = time.perf_counter()

    delta = end_at - start_at
    # since the capacity should have been fully refilled, second loop time
    # should take near zero time
    expected = await measure_zero(10)
    # drift is allowed to be up to 200% since we're working with very small
    # numbers.
    assert_fuzzy_equal(delta, expected, allowed_drift=2)


@pytest.mark.asyncio
async def test_token_bucket_can_take():
    bucket = TokenBucket(1, 10)

    assert bucket.can_take() is True  # can take 1
    assert bucket.can_take(bucket.get_num_tokens()) is True  # can take full capacity

    await bucket.take(10)  # empty the bucket

    assert bucket.can_take() is False


@pytest.mark.asyncio
async def test_token_bucket_get_num_tokens():
    bucket = TokenBucket(1, 10)

    # starts at full capacity
    assert bucket.get_num_tokens() == 10

    await bucket.take(5)
    assert 5 <= bucket.get_num_tokens() <= 5.1

    await bucket.take(bucket.get_num_tokens())

    assert 0 <= bucket.get_num_tokens() <= 0.1


def test_token_bucket_take_nowait():
    bucket = TokenBucket(1, 10)

    assert bucket.can_take(10)
    bucket.take_nowait(10)
    assert not bucket.can_take(1)

    with pytest.raises(NotEnoughTokens):
        bucket.take_nowait(1)
