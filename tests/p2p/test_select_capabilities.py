import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils.toolz import groupby

from p2p.handshake import _select_capabilities


A1 = ('A', 1)
A2 = ('A', 2)
B1 = ('B', 1)
B2 = ('B', 2)


@pytest.mark.parametrize(
    'remote_caps,local_caps,expected',
    (
        # simple case of single cap
        ((A1,), (A1,), (A1,)),
        ((B1,), (B1,), (B1,)),
        # simple case of multiple caps
        ((A1, B1), (A1, B1), (A1, B1)),
        # same simple cases but with ordering changed
        ((A1, B1), (B1, A1), (A1, B1)),
        ((B1, A1), (A1, B1), (A1, B1)),
        ((B1, A1), (B1, A1), (A1, B1)),
        # multiple of same proto full overlap
        ((A1, A2), (A2,), (A2,)),
        ((A1, A2), (A1,), (A1,)),
        # multiple of same proto partial overlap
        ((A1,), (A1, A2), (A1,)),
        ((A2,), (A1, A2), (A2,)),
        # multiple protocols, multiple versions
        ((A1, B1, A2, B2), (A1, B1, A2, B2), (A2, B2)),
        ((A1, B1, A2, B2), (A1, B1, A2), (A2, B1)),
        ((A1, B1, B2), (A1, B1, A2, B2), (A1, B2)),
        # multiple protocols, not all overlap
        ((A1, B1, A2, B2), (A1, A2), (A2,)),
        ((A1, B1, B2), (A1, A2), (A1,)),
        # no matches
        ((A1,), (A2,), ()),
        ((A2,), (A1,), ()),
        ((B1,), (A1,), ()),
        ((B1, A1), (B2, A2), ()),
        ((B1, B2), (A1, A2), ()),
        ((A1, B1, B2), (A2,), ()),
    )
)
def test_select_p2p_capabiltiies(remote_caps, local_caps, expected):
    actual = _select_capabilities(remote_caps, local_caps)
    assert actual == expected


cap_st = st.tuples(
    st.binary(min_size=1, max_size=5),
    st.integers(min_value=0, max_value=10),
)


@given(
    remote_caps=st.lists(cap_st),
    local_caps=st.lists(cap_st),
)
def test_select_p2p_capabiltiies_fuzzy(remote_caps, local_caps):
    common_caps = set(remote_caps).intersection(local_caps)
    common_caps_by_name = groupby(lambda cap: cap[0], common_caps)

    selected_caps = _select_capabilities(remote_caps, local_caps)

    if not common_caps:
        assert len(selected_caps) == 0
    else:
        # must be a subset of the common capabilities
        assert set(selected_caps).issubset(common_caps)

        # must be alphabetically sorted by capability name
        sorted_caps = tuple(sorted(selected_caps, key=lambda cap: cap[0]))
        assert sorted_caps == selected_caps

        # for each name, should be the highest common version
        for name, version in selected_caps:
            greatest_common_version = max((version for name, version in common_caps_by_name[name]))
            assert greatest_common_version == version
