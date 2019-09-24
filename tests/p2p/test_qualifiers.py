import pytest

from async_generator import asynccontextmanager

from p2p.abc import ConnectionAPI, LogicAPI
from p2p.logic import BaseLogic
from p2p.qualifiers import (
    qualifier,
    BaseQualifier,
    AndQualifier,
    OrQualifier,
    HasProtocol,
    HasCommand,
)

from p2p.tools.factories import CommandFactory, ParagonPeerPairFactory, ProtocolFactory
from p2p.tools.paragon import ParagonProtocol, BroadcastData


class SimpleLogic(BaseLogic):
    @asynccontextmanager
    async def apply(self, connection):
        yield


@pytest.fixture
async def alice_and_bob():
    async with ParagonPeerPairFactory() as (alice, bob):
        yield (alice, bob)


@pytest.fixture
def alice(alice_and_bob):
    alice, _ = alice_and_bob
    return alice.connection


@pytest.fixture
def bob(alice_and_bob):
    _, bob = alice_and_bob
    return bob.connection


@pytest.fixture
def my_logic():
    return SimpleLogic()


def test_and_qualifier(alice, bob, my_logic):
    def _is_alice(connection, logic):
        assert isinstance(alice, ConnectionAPI)
        return connection is alice

    def _is_my_logic(connection, logic):
        assert isinstance(logic, LogicAPI)
        return logic is my_logic

    qualifier = AndQualifier(_is_alice, _is_my_logic)

    assert qualifier(alice, my_logic) is True
    assert qualifier(bob, my_logic) is False
    assert qualifier(alice, SimpleLogic()) is False
    assert qualifier(bob, SimpleLogic()) is False


def test_or_qualifier(alice, my_logic):
    def _is_alice(connection, logic):
        assert isinstance(alice, ConnectionAPI)
        return connection is alice

    def _is_my_logic(connection, logic):
        assert isinstance(logic, LogicAPI)
        return logic is my_logic

    qualifier = OrQualifier(_is_alice, _is_my_logic)

    assert qualifier(alice, my_logic) is True
    assert qualifier(bob, my_logic) is True
    assert qualifier(alice, SimpleLogic()) is True
    assert qualifier(bob, SimpleLogic()) is False


def test_qualifier_fn_decorator(alice, bob, my_logic):
    @qualifier
    def _is_alice(connection, logic):
        assert isinstance(connection, ConnectionAPI)
        return connection is alice

    assert isinstance(_is_alice, BaseQualifier)

    assert _is_alice(alice, my_logic) is True
    assert _is_alice(bob, my_logic) is False


def test_combining_qualifiers(alice, bob, my_logic):
    @qualifier
    def _is_alice(connection, logic):
        assert isinstance(connection, ConnectionAPI)
        return connection is alice

    @qualifier
    def _is_my_logic(connection, logic):
        assert isinstance(logic, LogicAPI)
        return logic is my_logic

    is_alice_and_my_logic = _is_alice & _is_my_logic

    assert is_alice_and_my_logic(alice, my_logic) is True
    assert is_alice_and_my_logic(bob, my_logic) is False
    assert is_alice_and_my_logic(alice, SimpleLogic()) is False
    assert is_alice_and_my_logic(bob, SimpleLogic()) is False

    is_alice_or_my_logic = _is_alice | _is_my_logic

    assert is_alice_or_my_logic(alice, my_logic) is True
    assert is_alice_or_my_logic(bob, my_logic) is True
    assert is_alice_or_my_logic(alice, SimpleLogic()) is True
    assert is_alice_or_my_logic(bob, SimpleLogic()) is False


def test_has_protocol_qualifier(alice, my_logic):
    MyProtocol = ProtocolFactory()

    has_my_protocol = HasProtocol(MyProtocol)
    has_paragon = HasProtocol(ParagonProtocol)

    assert has_paragon(alice, my_logic) is True
    assert has_my_protocol(alice, my_logic) is False


def test_has_command_qualifier(alice, my_logic):
    MyCommand = CommandFactory()

    has_my_command = HasCommand(MyCommand)
    has_broadcast_data = HasCommand(BroadcastData)

    assert has_broadcast_data(alice, my_logic) is True
    assert has_my_command(alice, my_logic) is False
