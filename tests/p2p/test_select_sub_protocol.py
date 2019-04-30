import pytest

from p2p.exceptions import NoMatchingPeerCapabilities
from p2p.protocol import Protocol, select_sub_protocol


class BobV1(Protocol):
    name = 'bob'
    version = 1


class BobV2(Protocol):
    name = 'bob'
    version = 2


class AliceV1(Protocol):
    name = 'alice'
    version = 1


@pytest.mark.parametrize(
    'protocols,capabilities,expected',
    (
        ((BobV1,), (('bob', 1),), BobV1),
        ((BobV1,), (('bob', 1), ('bob', 2)), BobV1),
        ((BobV2,), (('bob', 1), ('bob', 2)), BobV2),
        ((BobV1, BobV2), (('bob', 1), ('bob', 2)), BobV2),
        ((BobV2, BobV1), (('bob', 1), ('bob', 2)), BobV2),
        # mixed
        ((BobV1,), (('bob', 1), ('alice', 1)), BobV1),
        ((BobV1,), (('bob', 1), ('alice', 3)), BobV1),
    ),
)
def test_sub_protocol_selection(protocols, capabilities, expected):
    actual = select_sub_protocol(protocols, capabilities)
    assert actual is expected


@pytest.mark.parametrize(
    'protocols,capabilities',
    (
        ((BobV1,), (('bob', 2),)),
        ((BobV1, BobV2), (('bob', 3),)),
        ((BobV1,), (('alice', 1),)),
        ((BobV2,), (('bob', 1),)),
    ),
)
def test_sub_protocol_selection_without_match(protocols, capabilities):
    with pytest.raises(NoMatchingPeerCapabilities):
        select_sub_protocol(protocols, capabilities)


def test_sub_protocol_selection_does_not_support_multiple_names():
    with pytest.raises(NotImplementedError):
        select_sub_protocol((BobV1, AliceV1), (('bob', 1), ('alice', 1)))
