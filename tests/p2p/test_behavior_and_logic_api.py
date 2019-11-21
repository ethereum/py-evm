import asyncio
import pytest

from async_generator import asynccontextmanager

from eth_utils import ValidationError

from p2p.p2p_proto import Ping
from p2p.behaviors import Behavior
from p2p.logic import (
    BaseLogic,
    Application,
    CommandHandler,
)
from p2p.qualifiers import always

from p2p.tools.factories import ConnectionPairFactory


class SimpleLogic(BaseLogic):
    @asynccontextmanager
    async def apply(self, connection):
        yield


@pytest.fixture
async def alice_and_bob():
    async with ConnectionPairFactory() as (alice, bob):
        yield (alice, bob)


@pytest.fixture
def alice(alice_and_bob):
    alice, _ = alice_and_bob
    return alice


@pytest.fixture
def bob(alice_and_bob):
    _, bob = alice_and_bob
    return bob


def test_behaviour_should_apply(alice):
    def _is_alice(connection, logic):
        return connection is alice

    behavior = Behavior(_is_alice, SimpleLogic())

    assert behavior.should_apply_to(alice) is True
    assert behavior.should_apply_to(bob) is False


@pytest.mark.asyncio
async def test_behavior_reentrance_protection(alice):
    behavior = Behavior(always, SimpleLogic())
    async with behavior.apply(alice):
        with pytest.raises(ValidationError, match="Reentrance: Behavior"):
            async with behavior.apply(alice):
                # this block should not be hit
                raise AssertionError("should not be hit")


@pytest.mark.asyncio
async def test_behavior_logic_reuse_protection_on_apply(alice):
    logic = SimpleLogic()
    behavior_a = Behavior(always, logic)
    behavior_b = Behavior(always, logic)
    async with behavior_a.apply(alice):
        with pytest.raises(ValidationError, match="Reentrance: Logic"):
            async with behavior_b.apply(alice):
                # this block should not be hit
                raise AssertionError("should not be hit")


def test_logic_as_behavior_with_local_qualifier(alice, bob):
    def _is_alice(connection, logic):
        return connection is alice

    class WithLocalQualifier(SimpleLogic):
        qualifier = staticmethod(_is_alice)

    logic = WithLocalQualifier()
    behavior = logic.as_behavior()

    assert behavior.should_apply_to(alice) is True
    assert behavior.should_apply_to(bob) is False


def test_logic_as_behavior_with_qualifier_override():
    def _is_alice(connection, logic):
        return connection is alice

    def _is_bob(connection, logic):
        return connection is bob

    class WithLocalQualifier(SimpleLogic):
        qualifier = staticmethod(_is_alice)

    logic = WithLocalQualifier()
    behavior = logic.as_behavior(_is_bob)

    assert behavior.should_apply_to(alice) is False
    assert behavior.should_apply_to(bob) is True


def test_logic_as_behavior_with_no_local_qualifier():
    logic = SimpleLogic()

    def _is_alice(connection, logic):
        return connection is alice

    with pytest.raises(TypeError):
        behavior = logic.as_behavior()

    behavior = logic.as_behavior(_is_alice)

    assert behavior.should_apply_to(alice) is True
    assert behavior.should_apply_to(bob) is False


@pytest.mark.asyncio
async def test_command_handler_logic():
    got_ping = asyncio.Event()

    class HandlePing(CommandHandler):
        command_type = Ping

        async def handle(self, connection, msg):
            got_ping.set()

    async with ConnectionPairFactory() as (alice, bob):
        ping_handler = HandlePing()
        async with ping_handler.as_behavior().apply(alice):
            bob.get_base_protocol().send(Ping(None))
            await asyncio.wait_for(got_ping.wait(), timeout=2)


@pytest.mark.asyncio
async def test_behavior_application():
    class MyApp(Application):
        name = 'app-name'
        qualifier = always

    async with ConnectionPairFactory() as (alice, bob):
        # ensure the API isn't already registered
        assert not alice.has_logic('app-name')
        async with MyApp().as_behavior().apply(alice):
            # ensure it registers with the connect
            assert alice.has_logic('app-name')
            my_app = alice.get_logic('app-name', MyApp)
            assert isinstance(my_app, MyApp)
        # ensure it removes itself from the API on exit
        assert not alice.has_logic('app-name')
