import pytest

from p2p.protocol import Protocol, match_protocols_with_capabilities


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
        ((BobV1,), (('bob', 1),), (BobV1,)),
        ((BobV1,), (('bob', 1), ('bob', 2)), (BobV1,)),
        ((BobV2,), (('bob', 1), ('bob', 2)), (BobV2,)),
        ((BobV1, BobV2), (('bob', 1), ('bob', 2)), (BobV2,)),
        ((BobV2, BobV1), (('bob', 1), ('bob', 2)), (BobV2,)),
        # mixed
        ((BobV1,), (('bob', 1), ('alice', 1)), (BobV1,)),
        ((BobV1,), (('bob', 1), ('alice', 3)), (BobV1,)),
        ((BobV1,), (('bob', 2),), ()),
        # no match
        ((BobV1, BobV2), (('bob', 3),), ()),
        ((BobV1,), (('alice', 1),), ()),
        ((BobV2,), (('bob', 1),), ()),
        # multiple
        ((BobV1, AliceV1), (('bob', 1), ('alice', 1)), (AliceV1, BobV1)),
        ((BobV1, BobV2, AliceV1), (('bob', 2), ('alice', 1)), (AliceV1, BobV2)),
        ((BobV1, BobV2, AliceV1), (('bob', 1), ('bob', 2), ('alice', 1)), (AliceV1, BobV2)),
    ),
)
def test_sub_protocol_selection(protocols, capabilities, expected):
    actual = match_protocols_with_capabilities(protocols, capabilities)
    assert actual == expected
