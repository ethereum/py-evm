import asyncio
from types import MethodType
from typing import (
    Any,
    cast,
    Dict,
    Tuple,
)


from cancel_token import CancelToken

from p2p import ecies
from p2p import protocol
from p2p.disconnect import DisconnectReason
from p2p.exceptions import HandshakeFailure
from p2p.p2p_proto import Hello
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.protocol import (
    match_protocols_with_capabilities,
)


from .peer import (
    ParagonPeerFactory,
    ParagonContext,
)
from p2p.tools.factories import (
    MemoryTransportPairFactory,
    NodeFactory,
)


async def get_directly_linked_peers_without_handshake(
        alice_factory: BasePeerFactory = None,
        bob_factory: BasePeerFactory = None) -> Tuple[BasePeer, BasePeer]:
    """
    See get_directly_linked_peers().

    Neither the P2P handshake nor the sub-protocol handshake will be performed here.
    """
    cancel_token = CancelToken("get_directly_linked_peers_without_handshake")

    if alice_factory is None:
        alice_factory = ParagonPeerFactory(
            privkey=ecies.generate_privkey(),
            context=ParagonContext(),
            token=cancel_token,
        )

    if bob_factory is None:
        bob_factory = ParagonPeerFactory(
            privkey=ecies.generate_privkey(),
            context=ParagonContext(),
            token=cancel_token,
        )

    alice_remote = NodeFactory(pubkey=alice_factory.privkey.public_key)
    bob_remote = NodeFactory(pubkey=bob_factory.privkey.public_key)

    alice_transport, bob_transport = MemoryTransportPairFactory(
        alice_remote=alice_remote,
        alice_private_key=alice_factory.privkey,
        bob_remote=bob_remote,
        bob_private_key=bob_factory.privkey,
    )

    alice = alice_factory.create_peer(alice_transport)
    bob = bob_factory.create_peer(bob_transport)

    return alice, bob


async def get_directly_linked_peers(
        request: Any, event_loop: asyncio.AbstractEventLoop,
        alice_factory: BasePeerFactory = None,
        bob_factory: BasePeerFactory = None) -> Tuple[BasePeer, BasePeer]:
    """Create two peers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
    """
    alice, bob = await get_directly_linked_peers_without_handshake(
        alice_factory,
        bob_factory,
    )

    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(alice.do_p2p_handshake(), bob.do_p2p_handshake())

    assert alice.sub_proto.name == bob.sub_proto.name
    assert alice.sub_proto.version == bob.sub_proto.version
    assert alice.sub_proto.cmd_id_offset == bob.sub_proto.cmd_id_offset

    # Perform the handshake for the enabled sub-protocol.
    await asyncio.gather(alice.do_sub_proto_handshake(), bob.do_sub_proto_handshake())

    asyncio.ensure_future(alice.run())
    asyncio.ensure_future(bob.run())

    def finalizer() -> None:
        event_loop.run_until_complete(asyncio.gather(
            alice.cancel(),
            bob.cancel(),
            loop=event_loop,
        ))
    request.addfinalizer(finalizer)

    # wait for start
    await alice.events.started.wait()
    await bob.events.started.wait()

    # wait for boot
    await alice.boot_manager.events.finished.wait()
    await bob.boot_manager.events.finished.wait()

    return alice, bob


async def process_v4_p2p_handshake(
        self: BasePeer,
        cmd: protocol.Command,
        msg: protocol.Payload) -> None:
    """
    This function is the replacement to the existing process_p2p_handshake
    function.
    This is used to simulate the v4 P2PProtocol node.
    The only change that has been made is to remove the snappy support irrespective
    of whether the other client supports it or not.
    """
    msg = cast(Dict[str, Any], msg)
    if not isinstance(cmd, Hello):
        await self.disconnect(DisconnectReason.bad_protocol)
        raise HandshakeFailure(f"Expected a Hello msg, got {cmd}, disconnecting")

    # As far as a v4 P2PProtocol client is concerned,
    # it never support snappy compression
    snappy_support = False

    remote_capabilities = msg['capabilities']
    matched_proto_classes = match_protocols_with_capabilities(
        self.supported_sub_protocols,
        remote_capabilities,
    )
    if len(matched_proto_classes) == 1:
        self.sub_proto = matched_proto_classes[0](
            self.transport,
            self.base_protocol.cmd_length,
            snappy_support,
        )
    elif len(matched_proto_classes) > 1:
        raise NotImplementedError(
            f"Peer {self.remote} connection matched on multiple protocols "
            f"{matched_proto_classes}.  Support for multiple protocols is not "
            f"yet supported"
        )
    else:
        await self.disconnect(DisconnectReason.useless_peer)
        raise HandshakeFailure(
            f"No matching capabilities between us ({self.capabilities}) and {self.remote} "
            f"({remote_capabilities}), disconnecting"
        )

    self.logger.debug(
        "Finished P2P handshake with %s, using sub-protocol %s",
        self.remote, self.sub_proto)


async def get_directly_linked_v4_and_v5_peers(
        request: Any, event_loop: asyncio.AbstractEventLoop,
        alice_factory: BasePeerFactory = None,
        bob_factory: BasePeerFactory = None) -> Tuple[BasePeer, BasePeer]:
    """Create two peers with their readers/writers connected directly.

    The first peer's reader will write directly to the second's writer, and vice-versa.
    """
    alice, bob = await get_directly_linked_peers_without_handshake(
        alice_factory,
        bob_factory,
    )

    # Tweaking the P2P Protocol Versions for Alice
    alice.base_protocol.version = 4  # type: ignore  # mypy doesn't like us overwriting class variables  # noqa: E501
    alice.process_p2p_handshake = MethodType(process_v4_p2p_handshake, alice)  # type: ignore  # mypy still support method overwrites  # noqa: E501

    # Perform the base protocol (P2P) handshake.
    await asyncio.gather(alice.do_p2p_handshake(), bob.do_p2p_handshake())

    assert alice.sub_proto.name == bob.sub_proto.name
    assert alice.sub_proto.version == bob.sub_proto.version
    assert alice.sub_proto.cmd_id_offset == bob.sub_proto.cmd_id_offset

    # Perform the handshake for the enabled sub-protocol.
    await asyncio.gather(alice.do_sub_proto_handshake(), bob.do_sub_proto_handshake())

    asyncio.ensure_future(alice.run())
    asyncio.ensure_future(bob.run())

    def finalizer() -> None:
        event_loop.run_until_complete(asyncio.gather(
            alice.cancel(),
            bob.cancel(),
            loop=event_loop,
        ))
    request.addfinalizer(finalizer)

    # wait for start
    await alice.events.started.wait()
    await bob.events.started.wait()

    # wait for boot
    await alice.boot_manager.events.finished.wait()
    await bob.boot_manager.events.finished.wait()

    return alice, bob
