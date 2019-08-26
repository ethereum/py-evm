from eth_utils import ValidationError
from py_ecc.optimized_bls12_381 import curve_order
import pytest

from eth2._utils.bls import bls
from eth2._utils.bls.backends import AVAILABLE_BACKENDS, NoOpBackend
from eth2.beacon.constants import EMPTY_PUBKEY, EMPTY_SIGNATURE


def assert_pubkey(obj):
    assert isinstance(obj, bytes) and len(obj) == 48


def assert_signature(obj):
    assert isinstance(obj, bytes) and len(obj) == 96


@pytest.fixture
def domain():
    return (123).to_bytes(8, "big")


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
def test_sanity(backend, domain):
    bls.use(backend)
    msg_0 = b"\x32" * 32

    # Test: Verify the basic sign/verify process
    privkey_0 = 5566
    sig_0 = bls.sign(msg_0, privkey_0, domain)
    assert_signature(sig_0)
    pubkey_0 = bls.privtopub(privkey_0)
    assert_pubkey(pubkey_0)
    assert bls.verify(msg_0, pubkey_0, sig_0, domain)

    privkey_1 = 5567
    sig_1 = bls.sign(msg_0, privkey_1, domain)
    pubkey_1 = bls.privtopub(privkey_1)
    assert bls.verify(msg_0, pubkey_1, sig_1, domain)

    # Test: Verify signatures are correctly aggregated
    aggregated_signature = bls.aggregate_signatures([sig_0, sig_1])
    assert_signature(aggregated_signature)

    # Test: Verify pubkeys are correctly aggregated
    aggregated_pubkey = bls.aggregate_pubkeys([pubkey_0, pubkey_1])
    assert_pubkey(aggregated_pubkey)

    # Test: Verify with `aggregated_signature` and `aggregated_pubkey`
    assert bls.verify(msg_0, aggregated_pubkey, aggregated_signature, domain)

    # Test: `verify_multiple`
    msg_1 = b"\x22" * 32
    privkey_2 = 55688
    sig_2 = bls.sign(msg_1, privkey_2, domain)
    assert_signature(sig_2)
    pubkey_2 = bls.privtopub(privkey_2)
    assert_pubkey(pubkey_2)
    sig_1_2 = bls.aggregate_signatures([sig_1, sig_2])
    assert bls.verify_multiple(
        pubkeys=[pubkey_1, pubkey_2],
        message_hashes=[msg_0, msg_1],
        signature=sig_1_2,
        domain=domain,
    )


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
@pytest.mark.parametrize(
    "privkey",
    [
        (1),
        (5),
        (124),
        (735),
        (127409812145),
        (90768492698215092512159),
        (curve_order - 1),
    ],
)
def test_bls_core_succeed(backend, privkey, domain):
    bls.use(backend)
    msg = str(privkey).encode("utf-8")
    sig = bls.sign(msg, privkey, domain=domain)
    pub = bls.privtopub(privkey)
    assert bls.verify(msg, pub, sig, domain=domain)


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
@pytest.mark.parametrize("privkey", [(0), (curve_order), (curve_order + 1)])
def test_invalid_private_key(backend, privkey, domain):
    bls.use(backend)
    msg = str(privkey).encode("utf-8")
    with pytest.raises(ValueError):
        bls.privtopub(privkey)
    with pytest.raises(ValueError):
        bls.sign(msg, privkey, domain=domain)


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
def test_empty_aggregation(backend):
    bls.use(backend)
    assert bls.aggregate_pubkeys([]) == EMPTY_PUBKEY
    assert bls.aggregate_signatures([]) == EMPTY_SIGNATURE


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
def test_verify_empty_signatures(backend, domain):
    # Want EMPTY_SIGNATURE to fail in Trinity
    bls.use(backend)

    def validate():
        bls.validate(b"\x11" * 32, EMPTY_PUBKEY, EMPTY_SIGNATURE, domain)

    def validate_multiple_1():
        bls.validate_multiple(
            pubkeys=(), message_hashes=(), signature=EMPTY_SIGNATURE, domain=domain
        )

    def validate_multiple_2():
        bls.validate_multiple(
            pubkeys=(EMPTY_PUBKEY, EMPTY_PUBKEY),
            message_hashes=(b"\x11" * 32, b"\x12" * 32),
            signature=EMPTY_SIGNATURE,
            domain=domain,
        )

    if backend == NoOpBackend:
        validate()
        validate_multiple_1()
        validate_multiple_2()
    else:
        with pytest.raises(ValidationError):
            validate()
        with pytest.raises(ValidationError):
            validate_multiple_1()
        with pytest.raises(ValidationError):
            validate_multiple_2()


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
@pytest.mark.parametrize(
    "msg, privkeys",
    [
        (
            b"\x12" * 32,
            [1, 5, 124, 735, 127409812145, 90768492698215092512159, curve_order - 1],
        ),
        (b"\x34" * 32, [42, 666, 1274099945, 4389392949595]),
    ],
)
def test_signature_aggregation(backend, msg, privkeys, domain):
    bls.use(backend)
    sigs = [bls.sign(msg, k, domain=domain) for k in privkeys]
    pubs = [bls.privtopub(k) for k in privkeys]
    aggsig = bls.aggregate_signatures(sigs)
    aggpub = bls.aggregate_pubkeys(pubs)
    assert bls.verify(msg, aggpub, aggsig, domain=domain)


@pytest.mark.parametrize("backend", AVAILABLE_BACKENDS)
@pytest.mark.parametrize("msg_1, msg_2", [(b"\x12" * 32, b"\x34" * 32)])
@pytest.mark.parametrize(
    "privkeys_1, privkeys_2",
    [
        (tuple(range(1, 11)), tuple(range(1, 11))),
        ((1, 2, 3), (4, 5, 6, 7)),
        ((1, 2, 3), (2, 3, 4, 5)),
        ((1, 2, 3), ()),
        ((), (2, 3, 4, 5)),
    ],
)
def test_multi_aggregation(backend, msg_1, msg_2, privkeys_1, privkeys_2, domain):
    bls.use(backend)

    sigs_1 = [
        bls.sign(msg_1, k, domain=domain) for k in privkeys_1
    ]  # signatures to msg_1
    pubs_1 = [bls.privtopub(k) for k in privkeys_1]
    aggpub_1 = bls.aggregate_pubkeys(pubs_1)  # sig_1 to msg_1

    sigs_2 = [
        bls.sign(msg_2, k, domain=domain) for k in privkeys_2
    ]  # signatures to msg_2
    pubs_2 = [bls.privtopub(k) for k in privkeys_2]
    aggpub_2 = bls.aggregate_pubkeys(pubs_2)  # sig_2 to msg_2

    message_hashes = [msg_1, msg_2]
    pubs = [aggpub_1, aggpub_2]
    aggsig = bls.aggregate_signatures(sigs_1 + sigs_2)

    assert bls.verify_multiple(
        pubkeys=pubs, message_hashes=message_hashes, signature=aggsig, domain=domain
    )
