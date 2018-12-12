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
    verify,
    verify_multiple,
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
    domain = 0
    p1 = multiply(G1, privkey)
    p2 = multiply(G2, privkey)
    msg = str(privkey).encode('utf-8')
    msghash = hash_to_G2(msg, domain=domain)

    assert normalize(decompress_G1(compress_G1(p1))) == normalize(p1)
    assert normalize(decompress_G2(compress_G2(p2))) == normalize(p2)
    assert normalize(decompress_G2(compress_G2(msghash))) == normalize(msghash)
    sig = sign(msg, privkey, domain=domain)
    pub = privtopub(privkey)
    assert verify(msg, pub, sig, domain=domain)


@pytest.mark.parametrize(
    'msg, privkeys',
    [
        (b'cow', [1, 5, 124, 735, 127409812145, 90768492698215092512159, 0]),
        (b'dog', [42, 666, 1274099945, 4389392949595]),
    ]
)
def test_signature_aggregation(msg, privkeys):
    domain = 0
    sigs = [sign(msg, k, domain=domain) for k in privkeys]
    pubs = [privtopub(k) for k in privkeys]
    aggsig = aggregate_sigs(sigs)
    aggpub = aggregate_pubs(pubs)
    assert verify(msg, aggpub, aggsig, domain=domain)


@pytest.mark.parametrize(
    'msg_1, msg_2, privkeys',
    [
        (b'cow', b'wow', [1, 5, 124, 735, 127409812145, 90768492698215092512159, 0]),
    ]
)
def test_multi_aggregation(msg_1, msg_2, privkeys):
    domain = 0
    sigs_1 = [sign(msg_1, k, domain=domain) for k in privkeys]

    pubs_1 = [privtopub(k) for k in privkeys]
    aggsig_1 = aggregate_sigs(sigs_1)
    aggpub_1 = aggregate_pubs(pubs_1)

    sigs_2 = [sign(msg_2, k, domain=domain) for k in privkeys]
    pubs_2 = [privtopub(k) for k in privkeys]
    aggsig_2 = aggregate_sigs(sigs_2)
    aggpub_2 = aggregate_pubs(pubs_2)

    msgs = [msg_1, msg_2]
    pubs = [aggpub_1, aggpub_2]
    aggsig = aggregate_sigs([aggsig_1, aggsig_2])

    assert verify_multiple(
        pubs=pubs,
        msgs=msgs,
        sig=aggsig,
        domain=domain,
    )
