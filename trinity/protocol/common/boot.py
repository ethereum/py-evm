from typing import TYPE_CHECKING

from eth_utils import ValidationError

from eth.vm.forks import HomesteadVM

from p2p.exceptions import PeerConnectionLost
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeerBootManager

from trinity.exceptions import DAOForkCheckFailure

from .constants import CHAIN_SPLIT_CHECK_TIMEOUT

if TYPE_CHECKING:
    from .peer import BaseChainPeer  # noqa: F401


class DAOCheckBootManager(BasePeerBootManager):
    peer: 'BaseChainPeer'

    async def _run(self) -> None:
        try:
            await self.ensure_same_side_on_dao_fork()
        except DAOForkCheckFailure as err:
            self.logger.debug("DAO fork check with %s failed: %s", self.peer, err)
            self.peer.disconnect_nowait(DisconnectReason.useless_peer)

    async def ensure_same_side_on_dao_fork(self) -> None:
        """Ensure we're on the same side of the DAO fork as the given peer.

        In order to do that we have to request the DAO fork block and its parent, but while we
        wait for that we may receive other messages from the peer, which are returned so that they
        can be re-added to our subscribers' queues when the peer is finally added to the pool.
        """
        for start_block, vm_class in self.peer.context.vm_configuration:
            if not issubclass(vm_class, HomesteadVM):
                continue
            elif not vm_class.support_dao_fork:
                break
            elif start_block > vm_class.dao_fork_block_number:
                # VM comes after the fork, so stop checking
                break

            start_block = vm_class.dao_fork_block_number - 1

            try:
                headers = await self.peer.requests.get_block_headers(  # type: ignore
                    start_block,
                    max_headers=2,
                    reverse=False,
                    timeout=CHAIN_SPLIT_CHECK_TIMEOUT,
                )

            except (TimeoutError, PeerConnectionLost) as err:
                raise DAOForkCheckFailure(
                    f"Timed out waiting for DAO fork header from {self.peer}: {err}"
                ) from err
            except ValidationError as err:
                raise DAOForkCheckFailure(
                    f"Invalid header response during DAO fork check: {err}"
                ) from err

            if len(headers) != 2:
                raise DAOForkCheckFailure(
                    f"{self.peer} failed to return DAO fork check headers"
                )
            else:
                parent, header = headers

            try:
                vm_class.validate_header(header, parent, check_seal=True)
            except ValidationError as err:
                raise DAOForkCheckFailure(f"{self.peer} failed DAO fork check validation: {err}")
