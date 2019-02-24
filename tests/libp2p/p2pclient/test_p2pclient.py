import pytest

from multiaddr import (
    Multiaddr,
    protocols,
)

from libp2p.p2pclient import (
    config,
)
from libp2p.p2pclient.p2pclient import (
    Client,
    parse_conn_protocol,
)


@pytest.mark.parametrize(
    "maddr_str, expected_proto",
    (
        ("/unix/123", protocols.P_UNIX),
        ("/ip4/127.0.0.1/tcp/7777", protocols.P_IP4),
    ),
)
def test_parse_conn_protocol_valid(maddr_str, expected_proto):
    assert parse_conn_protocol(Multiaddr(maddr_str)) == expected_proto


@pytest.mark.parametrize(
    "maddr_str",
    (
        "/p2p/QmbHVEEepCi7rn7VL7Exxpd2Ci9NNB6ifvqwhsrbRMgQFP",
        "/onion/timaq4ygg2iegci7:1234",
    ),
)
def test_parse_conn_protocol_invalid(maddr_str):
    maddr = Multiaddr(maddr_str)
    with pytest.raises(ValueError):
        parse_conn_protocol(maddr)


@pytest.mark.parametrize(
    "control_maddr_str, listen_maddr_str",
    (
        ("/unix/123", "/ip4/127.0.0.1/tcp/7777"),
        ("/ip4/127.0.0.1/tcp/6666", "/ip4/127.0.0.1/tcp/7777"),
        ("/ip4/127.0.0.1/tcp/6666", "/unix/123"),
        ("/unix/456", "/unix/123"),
    ),
)
def test_client_ctor_control_listen_maddr(control_maddr_str, listen_maddr_str):
    c = Client(Multiaddr(control_maddr_str), Multiaddr(listen_maddr_str))
    assert c.control_maddr == Multiaddr(control_maddr_str)
    assert c.listen_maddr == Multiaddr(listen_maddr_str)


def test_client_ctor_default_control_listen_maddr():
    c = Client()
    assert c.control_maddr == Multiaddr(config.control_maddr_str)
    assert c.listen_maddr == Multiaddr(config.listen_maddr_str)
