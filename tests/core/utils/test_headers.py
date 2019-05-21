import pytest

from trinity._utils.headers import (
    skip_complete_headers,
)


async def return_true(header):
    return True


async def return_false(header):
    return False


async def is_odd(header):
    return header % 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers, check, expected_completed, expected_remaining",
    (
        ((), return_true, (), ()),
        ((), return_false, (), ()),
        ((1,), return_true, (1,), ()),
        ((1,), return_false, (), (1,)),
        ((2, 3), return_true, (2, 3), ()),
        ((2, 3), return_false, (), (2, 3)),
        ((5, 6), is_odd, (5,), (6,)),
        # should accept a generator
        ((_ for _ in range(0)), return_false, (), ()),
        ((_ for _ in range(0)), return_true, (), ()),
        ((i for i in range(3)), return_true, (0, 1, 2), ()),
        ((i for i in range(3)), return_false, (), (0, 1, 2)),
        ((i for i in range(1, 4)), is_odd, (1,), (2, 3)),
    ),
)
async def test_skip_complete_headers(headers, check, expected_completed, expected_remaining):
    # Nothing about skip_complete_headers actually depends on having a header, so
    # we use integers for easy testing.
    completed, remaining = await skip_complete_headers(headers, check)
    assert completed == expected_completed
    assert remaining == expected_remaining
