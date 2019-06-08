import pytest

from py_ecc.optimized_bls12_381 import (
    curve_order,
)

from eth2._utils.bls_bindings.chia_network.api import (
    aggregate_pubkeys,
    aggregate_signatures,
    privtopub,
    sign,
    verify,
    verify_multiple,
)


def assert_pubkey(obj):
    assert isinstance(obj, bytes) and len(obj) == 48


def assert_signature(obj):
    assert isinstance(obj, bytes) and len(obj) == 96


def test_sanity():
    msg_0 = b"\x32" * 32
    domain = 123

    # Test: Verify the basic sign/verify process
    privkey_0 = 5566
    sig_0 = sign(msg_0, privkey_0, domain)
    assert_signature(sig_0)
    pubkey_0 = privtopub(privkey_0)
    assert_pubkey(pubkey_0)
    assert verify(msg_0, pubkey_0, sig_0, domain)

    privkey_1 = 5567
    sig_1 = sign(msg_0, privkey_1, domain)
    pubkey_1 = privtopub(privkey_1)
    assert verify(msg_0, pubkey_1, sig_1, domain)

    # Test: Verify signatures are correctly aggregated
    aggregated_signature = aggregate_signatures([sig_0, sig_1])
    assert_signature(aggregated_signature)

    # Test: Verify pubkeys are correctly aggregated
    aggregated_pubkey = aggregate_pubkeys([pubkey_0, pubkey_1])
    assert_pubkey(aggregated_pubkey)

    # Test: Verify with `aggregated_signature` and `aggregated_pubkey`
    assert verify(msg_0, aggregated_pubkey, aggregated_signature, domain)

    # Test: `verify_multiple`
    msg_1 = b"x22" * 32
    privkey_2 = 55688
    sig_2 = sign(msg_1, privkey_2, domain)
    assert_signature(sig_2)
    pubkey_2 = privtopub(privkey_2)
    assert_pubkey(pubkey_2)
    sig_1_2 = aggregate_signatures([sig_1, sig_2])
    assert verify_multiple(
        pubkeys=[pubkey_1, pubkey_2],
        message_hashes=[msg_0, msg_1],
        signature=sig_1_2,
        domain=domain,
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
        (curve_order - 1),
    ]
)
def test_bls_core(privkey):
    domain = 0
    msg = str(privkey).encode('utf-8')
    sig = sign(msg, privkey, domain=domain)
    pub = privtopub(privkey)
    assert verify(msg, pub, sig, domain=domain)


@pytest.mark.parametrize(
    'msg, privkeys',
    [
        (b'\x12' * 32, [1, 5, 124, 735, 127409812145, 90768492698215092512159, curve_order - 1]),
        (b'\x34' * 32, [42, 666, 1274099945, 4389392949595]),
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
    'msg_1, msg_2',
    [
        (b'\x12' * 32, b'\x34' * 32)
    ]
)
@pytest.mark.parametrize(
    'privkeys_1, privkeys_2',
    [
        (tuple(range(1, 11)), tuple(range(1, 11))),
        ((1, 2, 3), (4, 5, 6, 7)),
        ((1, 2, 3), (2, 3, 4, 5)),
    ]
)
def test_multi_aggregation(msg_1, msg_2, privkeys_1, privkeys_2):
    domain = 0

    sigs_1 = [sign(msg_1, k, domain=domain) for k in privkeys_1]  # signatures to msg_1
    pubs_1 = [privtopub(k) for k in privkeys_1]
    aggsig_1 = aggregate_signatures(sigs_1)
    aggpub_1 = aggregate_pubkeys(pubs_1)  # sig_1 to msg_1

    sigs_2 = [sign(msg_2, k, domain=domain) for k in privkeys_2]  # signatures to msg_2
    pubs_2 = [privtopub(k) for k in privkeys_2]
    aggsig_2 = aggregate_signatures(sigs_2)
    aggpub_2 = aggregate_pubkeys(pubs_2)  # sig_2 to msg_2

    message_hashes = [msg_1, msg_2]
    pubs = [aggpub_1, aggpub_2]
    aggsig = aggregate_signatures([aggsig_1, aggsig_2])

    assert verify_multiple(
        pubkeys=pubs,
        message_hashes=message_hashes,
        signature=aggsig,
        domain=domain,
    )
