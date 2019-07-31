import pytest

from hypothesis import (
    given,
    strategies as st,
)

from eth_utils import (
    decode_hex,
)

from p2p.discv5.tags import (
    compute_tag,
    recover_source_id_from_tag
)


@given(
    st.binary(min_size=32, max_size=32),
    st.binary(min_size=32, max_size=32),
)
def test_source_recovery(source, destination):
    tag = compute_tag(source, destination)
    recovered_src = recover_source_id_from_tag(tag, destination)
    assert recovered_src == source


@pytest.mark.parametrize(("source", "destination", "tag"), (
    (
        decode_hex("0x0000000000000000000000000000000000000000000000000000000000000000"),
        decode_hex("0x0000000000000000000000000000000000000000000000000000000000000000"),
        decode_hex("66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"),
    ),
    (
        decode_hex("0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"),
        decode_hex("0x0000000000000000000000000000000000000000000000000000000000000000"),
        decode_hex("0x99978552079d428893703e74716071dff768eb7a911dcc4c6fd5a6e2f2a0d6da"),
    ),
    (
        decode_hex("0xf72d359a057d2c4dbb4502edd4b9ca5f71fe7f93357e733c5f18cadd754e30de"),
        decode_hex("0x4a0f699062a9871bd8ef06f94f51d338bba02aaaedefde860093ad5f1e64dc25"),
        decode_hex("0xa979df942382a64ea3ace81dd5ceb9d95c05ef3ef8e2515b4ab5e45638029b0a"),
    ),
))
def test_tags(source, destination, tag):
    assert compute_tag(source, destination) == tag
    assert recover_source_id_from_tag(tag, destination) == source
