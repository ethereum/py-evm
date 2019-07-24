import pytest

from p2p.constants import P2P_PROTOCOL_COMMAND_LENGTH
from p2p.protocol import Protocol, get_cmd_offsets


class With2(Protocol):
    cmd_length = 2


class With5(Protocol):
    cmd_length = 5


class With7(Protocol):
    cmd_length = 7


BASE_OFFSET = P2P_PROTOCOL_COMMAND_LENGTH


@pytest.mark.parametrize(
    'protocols,offsets',
    (
        ((), ()),
        ((With2,), (BASE_OFFSET,)),
        ((With5,), (BASE_OFFSET,)),
        ((With7,), (BASE_OFFSET,)),
        ((With2, With5), (BASE_OFFSET, BASE_OFFSET + 2)),
        ((With5, With2), (BASE_OFFSET, BASE_OFFSET + 5)),
        ((With7, With2, With5), (BASE_OFFSET, BASE_OFFSET + 7, BASE_OFFSET + 7 + 2)),
    ),
)
def test_get_cmd_offsets(protocols, offsets):
    actual = get_cmd_offsets(protocols)
    assert actual == offsets
