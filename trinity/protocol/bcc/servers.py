import itertools
from typing import (
    cast,
    Iterable,
    FrozenSet,
    Type,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    cons,
    sliding_window,
    take,
)

from cancel_token import CancelToken

from p2p import protocol
from p2p.peer import BasePeer
from p2p.protocol import Command

from eth.exceptions import BlockNotFound

from eth2.beacon.db.chain import BaseBeaconChainDB
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.typing import (
    SlotNumber,
)

from trinity.protocol.common.servers import BaseRequestServer
from trinity.protocol.bcc.commands import (
    GetBeaconBlocks,
    GetBeaconBlocksMessage,
)
from trinity.protocol.bcc.peer import (
    BCCPeer,
    BCCPeerPool,
)


class BCCRequestServer(BaseRequestServer):
    subscription_msg_types: FrozenSet[Type[Command]] = frozenset({
        GetBeaconBlocks,
    })

    def __init__(self,
                 db: BaseBeaconChainDB,
                 peer_pool: BCCPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(peer_pool, token)
        self.db = db

    async def _handle_msg(self, base_peer: BasePeer, cmd: Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(BCCPeer, base_peer)

        if isinstance(cmd, GetBeaconBlocks):
            await self._handle_get_beacon_blocks(peer, cast(GetBeaconBlocksMessage, msg))
        else:
            raise Exception("Invariant: Only subscribed to GetBeaconBlocks")

    async def _handle_get_beacon_blocks(self, peer: BCCPeer, msg: GetBeaconBlocksMessage) -> None:
        if not peer.is_operational:
            return

        request_id = msg["request_id"]
        max_blocks = msg["max_blocks"]
        block_slot_or_root = msg["block_slot_or_root"]

        try:
            if isinstance(block_slot_or_root, int):
                # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
                # per BeaconStateMachine fork
                start_block = self.db.get_canonical_block_by_slot(
                    SlotNumber(block_slot_or_root),
                    BeaconBlock,
                )
            elif isinstance(block_slot_or_root, bytes):
                # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
                # per BeaconStateMachine fork
                start_block = self.db.get_block_by_root(Hash32(block_slot_or_root), BeaconBlock)
            else:
                raise TypeError(
                    f"Invariant: unexpected type for 'block_slot_or_root': "
                    f"{type(block_slot_or_root)}"
                )
        except BlockNotFound:
            start_block = None

        if start_block is not None:
            self.logger.debug2(
                "%s requested %d blocks starting with %s",
                peer,
                max_blocks,
                start_block,
            )
            blocks = self._get_blocks(start_block, max_blocks)
        else:
            self.logger.debug2("%s requested unknown block %s", block_slot_or_root)
            blocks = ()

        self.logger.debug2("Replying to %s with %d blocks", peer, len(blocks))
        peer.sub_proto.send_blocks(blocks, request_id)

    @to_tuple
    def _get_blocks(self,
                    start_block: BaseBeaconBlock,
                    max_blocks: int) -> Iterable[BaseBeaconBlock]:
        if max_blocks < 0:
            raise Exception("Invariant: max blocks cannot be negative")

        if max_blocks == 0:
            return

        yield start_block

        blocks_generator = cons(start_block, (
            # TODO: pass accurate `block_class: Type[BaseBeaconBlock]` under
            # per BeaconStateMachine fork
            self.db.get_canonical_block_by_slot(slot, BeaconBlock)
            for slot in itertools.count(start_block.slot + 1)
        ))
        max_blocks_generator = take(max_blocks, blocks_generator)

        try:
            # ensure only a connected chain is returned (breaks might occur if the start block is
            # not part of the canonical chain or if the canonical chain changes during execution)
            for parent, child in sliding_window(2, max_blocks_generator):
                if child.parent_root == parent.hash:
                    yield child
                else:
                    break
        except BlockNotFound:
            return
