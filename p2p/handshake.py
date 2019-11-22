import asyncio
import functools
import operator
from typing import (
    cast,
    Iterable,
    NamedTuple,
    Sequence,
    Type,
    Tuple,
)

from cancel_token import CancelToken

from eth_utils import (
    get_extended_debug_logger,
    to_tuple,
)
from eth_utils.toolz import groupby, valmap

from eth_keys import keys

from p2p._utils import duplicates
from p2p.abc import (
    ConnectionAPI,
    HandshakerAPI,
    HandshakeReceiptAPI,
    MultiplexerAPI,
    NodeAPI,
    TransportAPI,
)
from p2p.connection import Connection
from p2p.constants import DEVP2P_V5
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    HandshakeFailure,
    HandshakeFailureTooManyPeers,
    NoMatchingPeerCapabilities,
)
from p2p.multiplexer import (
    stream_transport_messages,
    Multiplexer,
)
from p2p.p2p_proto import (
    DevP2PReceipt,
    Disconnect,
    Hello,
    HelloPayload,
    BaseP2PProtocol,
    P2PProtocolV4,
    P2PProtocolV5,
)
from p2p.protocol import get_cmd_offsets
from p2p.transport import Transport
from p2p.typing import (
    Capabilities,
    Capability,
)


class Handshaker(HandshakerAPI):
    """
    Base class that handles the handshake for a given protocol.  The primary
    justification for this class's existence is to house parameters that are
    needed for the protocol handshake.
    """
    logger = get_extended_debug_logger('p2p.handshake.Handshaker')


class DevP2PHandshakeParams(NamedTuple):
    client_version_string: str
    listen_port: int
    version: int

    def get_base_protocol_class(self) -> Type[BaseP2PProtocol]:
        if self.version == 5:
            return P2PProtocolV5
        elif self.version == 4:
            return P2PProtocolV4
        else:
            raise Exception(
                f"Unknown protocol version: {self.version}.  Expected one of "
                f"`4` or `5`"
            )


@to_tuple
def _select_capabilities(remote_capabilities: Capabilities,
                         local_capabilities: Capabilities) -> Iterable[Capability]:
    """
    Select the appropriate shared capabilities between local and remote.

    https://github.com/ethereum/devp2p/blob/master/rlpx.md#capability-messaging
    """
    # Determine the remote capabilities that intersect with our own.
    matching_capabilities = tuple(sorted(
        set(local_capabilities).intersection(remote_capabilities),
        key=operator.itemgetter(0),
    ))
    # generate a dictionary of each capability grouped by name and sorted by
    # version in descending order.
    sort_by_version = functools.partial(sorted, key=operator.itemgetter(1), reverse=True)
    capabilities_by_name = valmap(
        tuple,
        valmap(
            sort_by_version,
            groupby(operator.itemgetter(0), matching_capabilities),
        ),
    )

    # now we loop over the names that have a matching capability and return the
    # *highest* version one.
    for name in sorted(capabilities_by_name.keys()):
        yield capabilities_by_name[name][0]


async def _do_p2p_handshake(transport: TransportAPI,
                            capabilities: Capabilities,
                            p2p_handshake_params: DevP2PHandshakeParams,
                            base_protocol: BaseP2PProtocol,
                            token: CancelToken) -> Tuple[DevP2PReceipt, BaseP2PProtocol]:
    client_version_string, listen_port, p2p_version = p2p_handshake_params
    base_protocol.send(Hello(HelloPayload(
        client_version_string=client_version_string,
        capabilities=capabilities,
        listen_port=listen_port,
        version=p2p_version,
        remote_public_key=transport.public_key.to_bytes(),
    )))

    # The base `p2p` protocol handshake directly streams the messages as it has
    # strict requirements about receiving the `Hello` message first.
    async for _, cmd in stream_transport_messages(transport, base_protocol, token=token):
        if isinstance(cmd, Disconnect):
            if cmd.payload == DisconnectReason.TOO_MANY_PEERS:
                raise HandshakeFailureTooManyPeers(f"Peer disconnected because it is already full")

        if not isinstance(cmd, Hello):
            raise HandshakeFailure(
                f"First message across the DevP2P connection must be a Hello "
                f"msg, got {cmd}, disconnecting"
            )

        protocol: BaseP2PProtocol

        if base_protocol.version >= DEVP2P_V5:
            # Check whether to support Snappy Compression or not
            # based on other peer's p2p protocol version
            snappy_support = cmd.payload.version >= DEVP2P_V5

            if snappy_support:
                # Now update the base protocol to support snappy compression
                # This is needed so that Trinity is compatible with parity since
                # parity sends Ping immediately after handshake
                protocol = P2PProtocolV5(
                    transport,
                    command_id_offset=0,
                    snappy_support=True,
                )
            else:
                protocol = base_protocol
        else:
            protocol = base_protocol

        devp2p_receipt = DevP2PReceipt(
            protocol=protocol,
            version=cmd.payload.version,
            client_version_string=cmd.payload.client_version_string,
            capabilities=cmd.payload.capabilities,
            remote_public_key=cmd.payload.remote_public_key,
            listen_port=cmd.payload.listen_port,
        )
        break
    else:
        raise HandshakeFailure("DevP2P message stream exited before finishing handshake")

    return devp2p_receipt, protocol


async def negotiate_protocol_handshakes(transport: TransportAPI,
                                        p2p_handshake_params: DevP2PHandshakeParams,
                                        protocol_handshakers: Sequence[HandshakerAPI],
                                        token: CancelToken,
                                        ) -> Tuple[MultiplexerAPI, DevP2PReceipt, Tuple[HandshakeReceiptAPI, ...]]:  # noqa: E501
    """
    Negotiate the handshakes for both the base `p2p` protocol and the
    appropriate sub protocols.  The basic logic follows the following steps.

    * perform the base `p2p` handshake.
    * using the capabilities exchanged during the `p2p` handshake, select the
      appropriate sub protocols.
    * allow each sub-protocol to perform its own handshake.
    * return the established `Multiplexer` as well as the `HandshakeReceipt`
      objects from each handshake.
    """
    # The `p2p` Protocol class that will be used.
    p2p_protocol_class = p2p_handshake_params.get_base_protocol_class()

    # Collect our local capabilities, the set of (name, version) pairs for all
    # of the protocols that we support.
    local_capabilities = tuple(
        handshaker.protocol_class.as_capability()
        for handshaker
        in protocol_handshakers
    )

    # Verify that there are no duplicated local or remote capabilities
    duplicate_capabilities = duplicates(local_capabilities)
    if duplicate_capabilities:
        raise Exception(f"Duplicate local capabilities: {duplicate_capabilities}")

    # We create an *ephemeral* version of the base `p2p` protocol with snappy
    # compression disabled for the handshake.  As part of the handshake, a new
    # instance of this protocol will be created with snappy compression enabled
    # if it is supported by the protocol version.
    ephemeral_base_protocol = p2p_protocol_class(
        transport,
        command_id_offset=0,
        snappy_support=False,
    )

    # Perform the actual `p2p` protocol handshake.  We need the remote
    # capabilities data from the receipt to select the appropriate sub
    # protocols.
    devp2p_receipt, base_protocol = await _do_p2p_handshake(
        transport,
        local_capabilities,
        p2p_handshake_params,
        ephemeral_base_protocol,
        token,
    )

    # This data structure is simply for easy retrieval of the proper
    # `Handshaker` for each selected protocol.
    protocol_handshakers_by_capability = dict(zip(local_capabilities, protocol_handshakers))
    # Using our local capabilities and the ones transmitted by the remote
    # select the highest shared version of each shared protocol.
    selected_capabilities = _select_capabilities(
        devp2p_receipt.capabilities,
        local_capabilities,
    )
    # If there are no capability matches throw an exception.
    if len(selected_capabilities) < 1:
        raise NoMatchingPeerCapabilities(
            "Found no matching capabilities between self and peer:\n"
            f" - local : {tuple(sorted(local_capabilities))}\n"
            f" - remote: {devp2p_receipt.capabilities}"
        )

    # Retrieve the handshakers which correspond to the selected protocols.
    # These are needed to perform the actual handshake logic for each protocol.
    selected_handshakers = tuple(
        protocol_handshakers_by_capability[capability]
        for capability in selected_capabilities
    )
    # Grab the `Protocol` class for each of the selected protocols.  We need
    # this to compute the offsets for each protocol's command ids, as well as
    # for instantiation of the protocol instances.
    selected_protocol_types = tuple(
        handshaker.protocol_class
        for handshaker
        in selected_handshakers
    )
    # Compute the offsets for each protocol's command ids
    protocol_cmd_offsets = get_cmd_offsets(selected_protocol_types)
    # Now instantiate instances of each of the protocol classes.
    selected_protocols = tuple(
        protocol_class(transport, command_id_offset, base_protocol.snappy_support)
        for protocol_class, command_id_offset
        in zip(selected_protocol_types, protocol_cmd_offsets)
    )
    # Create `Multiplexer` to abstract all of the protocols into a single
    # interface to stream only messages relevant to the given protocol.
    multiplexer = Multiplexer(transport, base_protocol, selected_protocols, token=token)

    # This context manager runs a background task which reads messages off of
    # the `Transport` and feeds them into protocol specific queues.  Each
    # protocol is responsible for reading its own messages from that queue via
    # the `Multiplexer.stream_protocol_messages` API.
    async with multiplexer.multiplex():
        # Concurrently perform the handshakes for each protocol, gathering up
        # the returned receipts.
        protocol_receipts = cast(Tuple[HandshakeReceiptAPI, ...], await asyncio.gather(*(
            handshaker.do_handshake(multiplexer, protocol)
            for handshaker, protocol
            in zip(selected_handshakers, selected_protocols)
        )))
    # Return the `Multiplexer` object as well as the handshake receipts.  The
    # `Multiplexer` object acts as a container for the individual protocol
    # instances.
    return multiplexer, devp2p_receipt, protocol_receipts


async def dial_out(remote: NodeAPI,
                   private_key: keys.PrivateKey,
                   p2p_handshake_params: DevP2PHandshakeParams,
                   protocol_handshakers: Sequence[HandshakerAPI],
                   token: CancelToken) -> ConnectionAPI:
    """
    Perform the auth and P2P handshakes with the given remote.

    Return a `Connection` object housing all of the negotiated sub protocols.

    Raises UnreachablePeer if we cannot connect to the peer or
    HandshakeFailure if the remote disconnects before completing the
    handshake or if none of the sub-protocols supported by us is also
    supported by the remote.
    """
    transport = await Transport.connect(
        remote,
        private_key,
        token,
    )

    transport.logger.debug2("Initiating p2p handshake with %s", remote)
    try:
        multiplexer, devp2p_receipt, protocol_receipts = await negotiate_protocol_handshakes(
            transport=transport,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=protocol_handshakers,
            token=token,
        )
    except Exception:
        # Note: This is one of two places where we manually handle closing the
        # reader/writer connection pair in the event of an error during the
        # peer connection and handshake process.
        # See `p2p.auth.handshake` for the other.
        transport.close()
        await asyncio.sleep(0)
        raise

    transport.logger.debug2("Completed p2p handshake with %s", remote)
    connection = Connection(
        multiplexer=multiplexer,
        devp2p_receipt=devp2p_receipt,
        protocol_receipts=protocol_receipts,
        is_dial_out=True,
    )
    return connection


async def receive_dial_in(reader: asyncio.StreamReader,
                          writer: asyncio.StreamWriter,
                          private_key: keys.PrivateKey,
                          p2p_handshake_params: DevP2PHandshakeParams,
                          protocol_handshakers: Sequence[HandshakerAPI],
                          token: CancelToken) -> Connection:
    transport = await Transport.receive_connection(
        reader=reader,
        writer=writer,
        private_key=private_key,
        token=token,
    )
    try:
        multiplexer, devp2p_receipt, protocol_receipts = await negotiate_protocol_handshakes(
            transport=transport,
            p2p_handshake_params=p2p_handshake_params,
            protocol_handshakers=protocol_handshakers,
            token=token,
        )
    except Exception:
        # Note: This is one of two places where we manually handle closing the
        # reader/writer connection pair in the event of an error during the
        # peer connection and handshake process.
        # See `p2p.auth.handshake` for the other.
        transport.close()
        await asyncio.sleep(0)
        raise

    connection = Connection(
        multiplexer=multiplexer,
        devp2p_receipt=devp2p_receipt,
        protocol_receipts=protocol_receipts,
        is_dial_out=False,
    )
    return connection
