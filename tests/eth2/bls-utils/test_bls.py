import pytest

from py_ecc.optimized_bls12_381 import (
    b2,
    FQ2,
    is_on_curve,
)

from eth_utils import (
    big_endian_to_int,
)

from eth2.beacon._utils.hash import (
    hash_eth2,
)

from eth2._utils.bls import (
    _get_x_coordinate,
    G1,
    G2,
    hash_to_G2,
    compress_G1,
    compress_G2,
    decompress_G1,
    decompress_G2,
    signature_to_G2,
    normalize,
    multiply,
    sign,
    privtopub,
    aggregate_signatures,
    aggregate_pubkeys,
    verify,
    verify_multiple,
)


@pytest.mark.parametrize(
    'message,domain',
    [
        (b'hello', 0),
        (b'hello', 1),
        (b'foo', 0),
    ]
)
def test_get_x_coordinate(message, domain):
    x_coordinate = _get_x_coordinate(message, domain)
    domain_in_bytes = domain.to_bytes(8, 'big')
    assert x_coordinate == FQ2(
        [
            big_endian_to_int(hash_eth2(message + domain_in_bytes + b'\x01')),
            big_endian_to_int(hash_eth2(message + domain_in_bytes + b'\x02')),
        ]
    )


def test_hash_to_G2():
    message = b'helloworld'

    domain_1 = 1
    result_1 = hash_to_G2(message, domain_1)
    assert is_on_curve(result_1, b2)


def test_decompress_G2_with_no_modular_square_root_found():
    with pytest.raises(ValueError, match="Failed to find a modular squareroot"):
        decompress_G2(signature_to_G2(b'\x11' * 96))


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
    aggsig = aggregate_signatures(sigs)
    aggpub = aggregate_pubkeys(pubs)
    assert verify(msg, aggpub, aggsig, domain=domain)


@pytest.mark.parametrize(
    'msg_1, msg_2, privkeys_1, privkeys_2',
    [
        (b'cow', b'wow', tuple(range(10)), tuple(range(10))),
        (b'cow', b'wow', (0, 1, 2, 3), (4, 5, 6, 7)),
        (b'cow', b'wow', (0, 1, 2, 3), (2, 3, 4, 5)),
    ]
)
def test_multi_aggregation(msg_1, msg_2, privkeys_1, privkeys_2):
    domain = 0

    sigs_1 = [sign(msg_1, k, domain=domain) for k in privkeys_1]
    pubs_1 = [privtopub(k) for k in privkeys_1]
    aggsig_1 = aggregate_signatures(sigs_1)
    aggpub_1 = aggregate_pubkeys(pubs_1)

    sigs_2 = [sign(msg_2, k, domain=domain) for k in privkeys_2]
    pubs_2 = [privtopub(k) for k in privkeys_2]
    aggsig_2 = aggregate_signatures(sigs_2)
    aggpub_2 = aggregate_pubkeys(pubs_2)

    msgs = [msg_1, msg_2]
    pubs = [aggpub_1, aggpub_2]
    aggsig = aggregate_signatures([aggsig_1, aggsig_2])

    assert verify_multiple(
        pubkeys=pubs,
        messages=msgs,
        signature=aggsig,
        domain=domain,
    )
