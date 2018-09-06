from eth_typing import Hash32

from eth_utils import ValidationError

from eth.vm.forks import HomesteadVM

from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer
from p2p.exceptions import (
    PeerConnectionLost,
)

from trinity.exceptions import (
    DAOForkCheckFailure,
)

from .constants import (
    CHAIN_SPLIT_CHECK_TIMEOUT,
)


class TrinityPeer(BasePeer):
    head_td: int = None
    head_hash: Hash32 = None

    def __init__(self,
                 network_id: int,
                 headerdb: 'BaseAsyncHeaderDB') -> None:
        pass

    async def _boot(self) -> None:
        try:
            await self.ensure_same_side_on_dao_fork()
        except DAOForkCheckFailure as err:
            self.logger.debug("DAO fork check with %s failed: %s", self, err)
            await self.disconnect(DisconnectReason.useless_peer)
            return

    async def ensure_same_side_on_dao_fork(self) -> None:
        """Ensure we're on the same side of the DAO fork as the given peer.

        In order to do that we have to request the DAO fork block and its parent, but while we
        wait for that we may receive other messages from the peer, which are returned so that they
        can be re-added to our subscribers' queues when the peer is finally added to the pool.
        """
        for start_block, vm_class in self.vm_configuration:
            if not issubclass(vm_class, HomesteadVM):
                continue
            elif not vm_class.support_dao_fork:
                break
            elif start_block > vm_class.dao_fork_block_number:
                # VM comes after the fork, so stop checking
                break

            start_block = vm_class.dao_fork_block_number - 1

            try:
                headers = await self.requests.get_block_headers(  # type: ignore
                    start_block,
                    max_headers=2,
                    reverse=False,
                    timeout=CHAIN_SPLIT_CHECK_TIMEOUT,
                )

            except (TimeoutError, PeerConnectionLost) as err:
                raise DAOForkCheckFailure(
                    f"Timed out waiting for DAO fork header from {self}: {err}"
                ) from err
            except ValidationError as err:
                raise DAOForkCheckFailure(
                    f"Invalid header response during DAO fork check: {err}"
                ) from err

            if len(headers) != 2:
                raise DAOForkCheckFailure(
                    f"{self} failed to return DAO fork check headers"
                )
            else:
                parent, header = headers

            try:
                vm_class.validate_header(header, parent, check_seal=True)
            except ValidationError as err:
                raise DAOForkCheckFailure(f"{self} failed DAO fork check validation: {err}")

    @property
    async def genesis(self) -> BlockHeader:
        genesis_hash = await self.wait(
            self.headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER)))
        return await self.wait(self.headerdb.coro_get_block_header_by_hash(genesis_hash))

    @property
    async def _local_chain_info(self) -> 'ChainInfo':
        genesis = await self.genesis
        head = await self.wait(self.headerdb.coro_get_canonical_head())
        total_difficulty = await self.headerdb.coro_get_score(head.hash)
        return ChainInfo(
            block_number=head.block_number,
            block_hash=head.hash,
            total_difficulty=total_difficulty,
            genesis_hash=genesis.hash,
        )
