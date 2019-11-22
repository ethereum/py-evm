import asyncio
import logging
from types import (
    TracebackType,
)
from typing import (
    AsyncIterator,
    Iterable,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from eth2.beacon.chains.base import (
    BaseBeaconChain,
)
from eth2.beacon.constants import (
    ZERO_SIGNING_ROOT,
)
from eth2.beacon.helpers import (
    compute_start_slot_at_epoch,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
)
from eth2.beacon.typing import (
    Slot,
)
from eth.exceptions import (
    BlockNotFound,
)
from eth_keys import (
    datatypes,
)
from eth_utils import (
    ValidationError,
    get_extended_debug_logger,
    to_tuple,
)
from libp2p.network.stream.exceptions import (
    StreamEOF,
    StreamReset,
)
from libp2p.network.stream.net_stream_interface import (
    INetStream,
)
from libp2p.peer.id import (
    ID,
)
from libp2p.utils import (
    decode_uvarint_from_stream,
    encode_uvarint,
)
from multiaddr import (
    Multiaddr,
)
import multihash
import ssz
from ssz.sedes.serializable import (
    BaseSerializable,
)
from ssz.tools import (
    to_formatted_dict,
)

from .configs import (
    REQ_RESP_ENCODE_POSTFIX,
    REQ_RESP_PROTOCOL_PREFIX,
    REQ_RESP_VERSION,
    MAX_CHUNK_SIZE,
    RESP_TIMEOUT,
    TTFB_TIMEOUT,
    ResponseCode,
)
from .exceptions import (
    InvalidRequest,
    InvalidRequestSaidPeer,
    IrrelevantNetwork,
    ReadMessageFailure,
    ServerErrorSaidPeer,
    WriteMessageFailure,
)
from .messages import (
    BeaconBlocksByRangeRequest,
    Status,
    BeaconBlocksByRootRequest,
)

MsgType = TypeVar("MsgType", bound=BaseSerializable)

logger = logging.getLogger('trinity.protocol.bcc_libp2p')


def peer_id_from_pubkey(pubkey: datatypes.PublicKey) -> ID:
    algo = multihash.Func.sha2_256
    mh_digest = multihash.digest(pubkey.to_bytes(), algo)
    return ID(mh_digest.encode())


def make_tcp_ip_maddr(ip: str, port: int) -> Multiaddr:
    return Multiaddr(f"/ip4/{ip}/tcp/{port}")


def make_rpc_protocol_id(message_name: str, schema_version: str, encoding: str) -> str:
    return f"{REQ_RESP_PROTOCOL_PREFIX}/{message_name}/{schema_version}/{encoding}"


def make_rpc_v1_ssz_protocol_id(message_name: str) -> str:
    return make_rpc_protocol_id(message_name, REQ_RESP_VERSION, REQ_RESP_ENCODE_POSTFIX)


def get_my_status(chain: BaseBeaconChain) -> Status:
    state = chain.get_head_state()
    head = chain.get_canonical_head()
    finalized_checkpoint = state.finalized_checkpoint
    return Status(
        head_fork_version=state.fork.current_version,
        finalized_root=finalized_checkpoint.root,
        finalized_epoch=finalized_checkpoint.epoch,
        head_root=head.signing_root,
        head_slot=head.slot,
    )


async def validate_peer_status(chain: BaseBeaconChain, peer_status: Status) -> None:
    state_machine = chain.get_state_machine()
    state = chain.get_head_state()
    config = state_machine.config
    if peer_status.head_fork_version != state.fork.current_version:
        raise IrrelevantNetwork(
            "`fork_version` mismatches: "
            f"peer_status.head_fork_version={peer_status.head_fork_version}, "
            f"state.fork.current_version={state.fork.current_version}"
        )

    # Can not validate the checkpoint with `finalized_epoch` higher than ours
    if peer_status.finalized_epoch > state.finalized_checkpoint.epoch:
        return

    # Edge case where nothing is finalized yet
    if (
        peer_status.finalized_epoch == 0 and
        peer_status.finalized_root == ZERO_SIGNING_ROOT
    ):
        return

    finalized_epoch_start_slot = compute_start_slot_at_epoch(
        peer_status.finalized_epoch,
        config.SLOTS_PER_EPOCH,
    )
    finalized_root = chain.get_canonical_block_root(
        finalized_epoch_start_slot)

    if peer_status.finalized_root != finalized_root:
        raise IrrelevantNetwork(
            "`finalized_root` mismatches: "
            f"peer_status.finalized_root={peer_status.finalized_root.hex()}, "
            f"peer_status.finalized_epoch={peer_status.finalized_epoch}, "
            f"our `finalized_root` at the same `finalized_epoch`={finalized_root.hex()}"
        )


def compare_chain_tip_and_finalized_epoch(chain: BaseBeaconChain, peer_status: Status) -> None:
    checkpoint = chain.get_head_state().finalized_checkpoint
    head_block = chain.get_canonical_head()

    peer_has_higher_finalized_epoch = peer_status.finalized_epoch > checkpoint.epoch
    peer_has_equal_finalized_epoch = peer_status.finalized_epoch == checkpoint.epoch
    peer_has_higher_head_slot = peer_status.head_slot > head_block.slot
    if (
        peer_has_higher_finalized_epoch or
        (peer_has_equal_finalized_epoch and peer_has_higher_head_slot)
    ):
        # TODO: kickoff syncing process with this peer
        logger.debug("Peer's chain is ahead of us, start syncing with the peer.")
        pass


def validate_start_slot(chain: BaseBeaconChain, start_slot: Slot) -> None:
    config = chain.get_state_machine().config
    state = chain.get_head_state()
    finalized_epoch_start_slot = compute_start_slot_at_epoch(
        epoch=state.finalized_checkpoint.epoch,
        slots_per_epoch=config.SLOTS_PER_EPOCH,
    )
    if start_slot < finalized_epoch_start_slot:
        raise ValidationError(
            f"`start_slot`({start_slot}) lower than our"
            f" latest finalized slot({finalized_epoch_start_slot})"
        )


@to_tuple
def get_blocks_from_canonical_chain_by_slot(
    chain: BaseBeaconChain,
    slot_of_requested_blocks: Sequence[Slot],
) -> Iterable[BaseBeaconBlock]:
    # If peer's head block is on our canonical chain,
    # start getting the requested blocks by slots.
    for slot in slot_of_requested_blocks:
        try:
            block = chain.get_canonical_block_by_slot(slot)
        except BlockNotFound:
            pass
        else:
            yield block


@to_tuple
def get_blocks_from_fork_chain_by_root(
    chain: BaseBeaconChain,
    start_slot: Slot,
    peer_head_block: BaseBeaconBlock,
    slot_of_requested_blocks: Sequence[Slot],
) -> Iterable[BaseBeaconBlock]:
    # Peer's head block is on a fork chain,
    # start getting the requested blocks by
    # traversing the history from the head.

    # `slot_of_requested_blocks` starts with earliest slot
    # and end with most recent slot, so we start traversing
    # from the most recent slot.
    cur_index = len(slot_of_requested_blocks) - 1
    block = peer_head_block
    if block.slot == slot_of_requested_blocks[cur_index]:
        yield block
        cur_index -= 1
    while block.slot > start_slot and cur_index >= 0:
        try:
            block = chain.get_block_by_root(block.parent_root)
        except (BlockNotFound, ValidationError):
            # This should not happen as we only persist block if its
            # ancestors are also in the database.
            break
        else:
            while block.slot < slot_of_requested_blocks[cur_index]:
                if cur_index > 0:
                    cur_index -= 1
                else:
                    break
            if block.slot == slot_of_requested_blocks[cur_index]:
                yield block


def _get_requested_beacon_blocks(
    chain: BaseBeaconChain,
    beacon_blocks_request: BeaconBlocksByRangeRequest,
    requested_head_block: BaseBeaconBlock,
) -> Tuple[BaseBeaconBlock, ...]:
    slot_of_requested_blocks = tuple(
        beacon_blocks_request.start_slot + i * beacon_blocks_request.step
        for i in range(beacon_blocks_request.count)
    )
    logger.info("slot_of_requested_blocks: %s", slot_of_requested_blocks)
    slot_of_requested_blocks = tuple(
        filter(lambda slot: slot <= requested_head_block.slot, slot_of_requested_blocks)
    )

    if len(slot_of_requested_blocks) == 0:
        return tuple()

    # We have the peer's head block in our database,
    # next check if the head block is on our canonical chain.
    try:
        canonical_block_at_slot = chain.get_canonical_block_by_slot(
            requested_head_block.slot
        )
        block_match = canonical_block_at_slot == requested_head_block
    except BlockNotFound:
        logger.debug(
            (
                "The requested head block is not on our canonical chain  "
                "requested_head_block: %s"
            ),
            requested_head_block,
        )
        block_match = False
    finally:
        if block_match:
            # Peer's head block is on our canonical chain
            return get_blocks_from_canonical_chain_by_slot(
                chain,
                slot_of_requested_blocks,
            )
        else:
            # Peer's head block is not on our canonical chain
            # Validate `start_slot` is greater than our latest finalized slot
            validate_start_slot(chain, beacon_blocks_request.start_slot)
            return get_blocks_from_fork_chain_by_root(
                chain,
                beacon_blocks_request.start_slot,
                requested_head_block,
                slot_of_requested_blocks,
            )


def get_requested_beacon_blocks(
    chain: BaseBeaconChain,
    request: BeaconBlocksByRangeRequest
) -> Tuple[BaseBeaconBlock, ...]:
    try:
        requested_head = chain.get_block_by_root(
            request.head_block_root
        )
    except (BlockNotFound, ValidationError) as error:
        logger.info("Sending empty blocks, reason: %s", error)
        return tuple()

    # Check if slot of specified head block is greater than specified start slot
    if requested_head.slot < request.start_slot:
        raise InvalidRequest(
            f"head block slot({requested_head.slot}) lower than `start_slot`({request.start_slot})"
        )

    try:
        requested_beacon_blocks = _get_requested_beacon_blocks(
            chain, request, requested_head
        )
        return requested_beacon_blocks
    except ValidationError as val_error:
        raise InvalidRequest(str(val_error))


@to_tuple
def get_beacon_blocks_by_root(
    chain: BaseBeaconChain,
    request: BeaconBlocksByRootRequest,
) -> Iterable[BaseBeaconBlock]:
    for block_root in request.block_roots:
        try:
            block = chain.get_block_by_root(block_root)
        except (BlockNotFound, ValidationError):
            pass
        else:
            yield block


# TODO: Refactor: Probably move these [de]serialization functions to `Node` as methods,
#   expose the hard-coded to parameters, and pass the timeout from the methods?

class Interaction:
    stream: INetStream
    logger = get_extended_debug_logger("trinity.protocol.bcc_libp2p.Interaction")

    def __init__(self, stream: INetStream):
        self.stream = stream

    async def __aenter__(self) -> "Interaction":
        self.debug("Started")
        return self

    async def __aexit__(self,
                        exc_type: Optional[Type[BaseException]],
                        exc_value: Optional[BaseException],
                        traceback: Optional[TracebackType],
                        ) -> None:
        await self.stream.close()
        self.debug("Ended")

    async def write_request(self, message: MsgType) -> None:
        self.debug(f"Request {type(message).__name__}  {to_formatted_dict(message)}")
        await write_req(self.stream, message)

    async def write_response(self, message: MsgType) -> None:
        self.debug(f"Respond {type(message).__name__}  {to_formatted_dict(message)}")
        await write_resp(self.stream, message, ResponseCode.SUCCESS)

    async def write_chunk_response(self, messages: Sequence[MsgType]) -> None:
        self.debug(f"Respond {len(messages)} chunks")
        for message in messages:
            await write_resp(self.stream, message, ResponseCode.SUCCESS)

    async def write_error_response(self, error_message: str, code: ResponseCode) -> None:
        self.debug(f"Respond {str(code)}  {error_message}")
        await write_resp(self.stream, error_message, code)

    async def read_request(self, message_type: Type[MsgType]) -> MsgType:
        self.debug(f"Waiting {message_type.__name__}")
        request = await read_req(self.stream, message_type)
        self.debug(f"Received request {message_type.__name__}  {to_formatted_dict(request)}")
        return request

    async def read_response(self, message_type: Type[MsgType]) -> MsgType:
        response = await read_resp(self.stream, message_type)
        self.debug(
            f"Received response {message_type.__name__}  {to_formatted_dict(response)}"
        )
        return response

    async def read_chunk_response(
        self,
        message_type: Type[MsgType],
        count: int,
    ) -> AsyncIterator[MsgType]:
        for i in range(count):
            try:
                yield await read_resp(self.stream, message_type)
            except ReadMessageFailure:
                self.debug(f"Received {str(i)} {message_type.__name__} chunks")
                break

    @property
    def peer_id(self) -> ID:
        return self.stream.mplex_conn.peer_id

    def debug(self, message: str) -> None:
        self.logger.debug(
            "Interaction %s    with %s    %s",
            self.stream.get_protocol().split("/")[4],
            str(self.peer_id)[:15],
            message,
        )


async def read_req(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> MsgType:
    """
    Read a `MsgType` request message from the `stream`.
    `ReadMessageFailure` is raised if fail to read the message.
    """
    return await _read_ssz_stream(stream, msg_type, timeout=RESP_TIMEOUT)


async def write_req(
    stream: INetStream,
    msg: MsgType,
) -> None:
    """
    Write the request `msg` to the `stream`.
    `WriteMessageFailure` is raised if fail to write the message.
    """
    msg_bytes = _serialize_ssz_msg(msg)
    # TODO: Handle exceptions from stream?
    await _write_stream(stream, msg_bytes)


async def read_resp(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> MsgType:
    """
    Read a `MsgType` response message from the `stream`.
    `ReadMessageFailure` is raised if fail to read the message.
    Returns the error message(type `str`) if the response code is not SUCCESS, otherwise returns
    the `MsgType` response message.
    """
    result_bytes = await _read_stream(stream, 1, TTFB_TIMEOUT)
    if len(result_bytes) != 1:
        raise ReadMessageFailure(
            f"result bytes should be of length 1: result_bytes={result_bytes!r}"
        )
    try:
        resp_code = ResponseCode(result_bytes[0])
    except ValueError:
        raise ReadMessageFailure(f"unknown resp_code={result_bytes[0]}")
    if resp_code == ResponseCode.SUCCESS:
        return await _read_ssz_stream(stream, msg_type, timeout=RESP_TIMEOUT)
    # error message
    else:
        msg_bytes = await _read_varint_prefixed_bytes(stream, timeout=RESP_TIMEOUT)
        msg = msg_bytes.decode("utf-8")
        if resp_code == ResponseCode.INVALID_REQUEST:
            raise InvalidRequestSaidPeer(msg)
        elif resp_code == ResponseCode.SERVER_ERROR:
            raise ServerErrorSaidPeer(msg)
        else:
            raise Exception("Invariant: Should not reach here")


async def write_resp(
    stream: INetStream,
    msg: Union[MsgType, str],
    resp_code: ResponseCode,
) -> None:
    """
    Write either a `MsgType` response message or an error message to the `stream`.
    `WriteMessageFailure` is raised if fail to read the message.
    """
    try:
        resp_code_byte = resp_code.value.to_bytes(1, "big")
    except OverflowError as error:
        raise WriteMessageFailure(f"resp_code={resp_code} is not valid") from error
    msg_bytes: bytes
    # MsgType: `msg` is of type `BaseSerializable` if response code is success.
    if resp_code == ResponseCode.SUCCESS:
        if isinstance(msg, BaseSerializable):
            msg_bytes = _serialize_ssz_msg(msg)
        else:
            raise WriteMessageFailure(
                "type of `msg` should be `BaseSerializable` if response code is SUCCESS, "
                f"type(msg)={type(msg)}"
            )
    # error msg is of type `str` if response code is not SUCCESS.
    else:
        if isinstance(msg, str):
            msg_bytes = _serialize_bytes(msg.encode("utf-8"))
        else:
            raise WriteMessageFailure(
                "type of `msg` should be `str` if response code is not SUCCESS, "
                f"type(msg)={type(msg)}"
            )
    # TODO: Optimization: probably the first byte should be written
    #   at the beginning of this function, to meet the limitation of `TTFB_TIMEOUT`.
    # TODO: Handle exceptions from stream?
    await _write_stream(stream, resp_code_byte + msg_bytes)


async def _write_stream(stream: INetStream, data: bytes) -> None:
    try:
        await stream.write(data)
    except StreamEOF as error:
        await stream.close()
        raise WriteMessageFailure() from error
    except StreamReset as error:
        raise WriteMessageFailure() from error


async def _read_stream(stream: INetStream, len_payload: int, timeout: float) -> bytes:
    try:
        return await asyncio.wait_for(stream.read(len_payload), timeout)
    except asyncio.TimeoutError:
        raise ReadMessageFailure("Timeout")
    except StreamEOF as error:
        await stream.close()
        raise ReadMessageFailure() from error
    except StreamReset as error:
        raise ReadMessageFailure() from error


async def _decode_uvarint_from_stream(stream: INetStream, timeout: float) -> None:
    try:
        return await asyncio.wait_for(decode_uvarint_from_stream(stream), timeout)
    except asyncio.TimeoutError:
        raise ReadMessageFailure("Timeout")
    except StreamEOF as error:
        await stream.close()
        raise ReadMessageFailure() from error
    except StreamReset as error:
        raise ReadMessageFailure() from error


async def _read_varint_prefixed_bytes(
    stream: INetStream,
    timeout: float = None,
) -> bytes:
    len_payload = await _decode_uvarint_from_stream(stream, timeout)
    if len_payload > MAX_CHUNK_SIZE:
        raise ReadMessageFailure(
            f"size_of_payload={len_payload} is larger than maximum={MAX_CHUNK_SIZE}"
        )
    payload = await _read_stream(stream, len_payload, timeout)
    if len(payload) != len_payload:
        raise ReadMessageFailure(f"expected {len_payload} bytes, but only read {len(payload)}")
    return payload


async def _read_ssz_stream(
    stream: INetStream,
    msg_type: Type[MsgType],
    timeout: float = None,
) -> MsgType:
    payload = await _read_varint_prefixed_bytes(stream, timeout=timeout)
    return _read_ssz_msg(payload, msg_type)


def _read_ssz_msg(
    payload: bytes,
    msg_type: Type[MsgType],
) -> MsgType:
    try:
        return ssz.decode(payload, msg_type)
    except (TypeError, ssz.DeserializationError) as error:
        raise ReadMessageFailure("failed to read the payload") from error


def _serialize_bytes(payload: bytes) -> bytes:
    len_payload_varint = encode_uvarint(len(payload))
    return len_payload_varint + payload


def _serialize_ssz_msg(msg: MsgType) -> bytes:
    try:
        msg_bytes = ssz.encode(msg)
        return _serialize_bytes(msg_bytes)
    except ssz.SerializationError as error:
        raise WriteMessageFailure(f"failed to serialize msg={msg}") from error
