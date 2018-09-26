import pytest

from eth.utils.bls import (
    G1,
    G2,
    hash_to_G2,
    compress_G1,
    compress_G2,
    decompress_G1,
    decompress_G2,
    normalize,
    multiply,
    sign,
    privtopub,
    aggregate_sigs,
    aggregate_pubs,
    verify
)


@pytest.mark.parametrize(
    'privkey',
    [
        (1),
        (5),
        (124),
        (735),
        (127409812145),
        (90768492698215092512159),
        (0),
    ]
)
def test_bls_core(privkey):
    p1 = multiply(G1, privkey)
    p2 = multiply(G2, privkey)
    msg = str(privkey).encode('utf-8')
    msghash = hash_to_G2(msg)
    assert normalize(decompress_G1(compress_G1(p1))) == normalize(p1)
    assert normalize(decompress_G2(compress_G2(p2))) == normalize(p2)
    assert normalize(decompress_G2(compress_G2(msghash))) == normalize(msghash)
    sig = sign(msg, privkey)
    pub = privtopub(privkey)
    assert verify(msg, pub, sig)


@pytest.mark.parametrize(
    'msg, privkeys',
    [
        (b'cow', [1, 5, 124, 735, 127409812145, 90768492698215092512159, 0]),
        (b'dog', [42, 666, 1274099945, 4389392949595]),
    ]
)
def test_signature_aggregation(msg, privkeys):
    sigs = [sign(msg, k) for k in privkeys]
    pubs = [privtopub(k) for k in privkeys]
    aggsig = aggregate_sigs(sigs)
    aggpub = aggregate_pubs(pubs)
    assert verify(msg, aggpub, aggsig)
