import pytest

from p2p.chain import HeaderRequest
from p2p.eth import MAX_HEADERS_FETCH


@pytest.mark.parametrize(
    "request_params,expected",
    (
        # (forward) starting at zero
        ((0, 5, 0, False), (0, 1, 2, 3, 4)),
        ((0, 5, 1, False), (0, 2, 4, 6, 8)),
        ((0, 5, 1, False), (0, 2, 4, 6, 8)),
        ## (forward) starting above zero
        #((101, 10, 0, False), tuple(range(101, 111))),
        #((101, 10, 1, False), tuple(range(101, 111, 2))),
        #((101, 10, 3, False), tuple(range(101, 111, 4))),
        ## (forward) exceeding MAX_HEADERS_FETCH
        #((0, 200, 0, False), tuple(range(MAX_HEADERS_FETCH))),
        ## (reverse)
        #((100, 10, 0, True), tuple(range(100, 90, -1))),
        #((100, 10, 1, True), tuple(range(100, 90, -2))),
    )
)
def test_block_number_generation(request_params, expected):
    header_request = HeaderRequest(*request_params)
    actual = header_request.generate_block_numbers()
    assert actual == expected
