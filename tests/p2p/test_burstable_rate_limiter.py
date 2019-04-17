import pytest
import time

from p2p._utils import burstable_rate_limiter


@pytest.mark.asyncio
async def test_burstable_rate_limiter_hits_limit():
    limiter = burstable_rate_limiter(5, 0.01)

    start_at = time.perf_counter()
    for _ in range(25):
        await limiter.__anext__()

    end_at = time.perf_counter()
    delta = end_at - start_at
    assert abs(delta - 0.05) < 0.01


@pytest.mark.asyncio
async def test_burstable_rate_limiter_allows_burst():
    limiter = burstable_rate_limiter(10, 0.01)

    start_at = time.perf_counter()
    for _ in range(10):
        await limiter.__anext__()

    end_at = time.perf_counter()
    delta = end_at - start_at
    assert delta < 0.001
