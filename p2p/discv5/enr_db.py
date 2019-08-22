import logging
from typing import (
    Dict,
)

import trio

from eth_utils import encode_hex

from p2p.discv5.abc import EnrDbApi
from p2p.discv5.enr import ENR
from p2p.discv5.identity_schemes import IdentitySchemeRegistry
from p2p.discv5.typing import NodeID


class BaseEnrDb(EnrDbApi):

    def __init__(self, identity_scheme_registry: IdentitySchemeRegistry):
        self.logger = logging.getLogger(".".join((
            self.__module__,
            self.__class__.__name__,
        )))
        self._identity_scheme_registry = identity_scheme_registry

    @property
    def identity_scheme_registry(self) -> IdentitySchemeRegistry:
        return self._identity_scheme_registry

    def validate_identity_scheme(self, enr: ENR) -> None:
        """Check that we know the identity scheme of the ENR.

        This check should be performed whenever an ENR is inserted or updated in serialized form to
        make sure retrieving it at a later time will succeed (deserializing the ENR would fail if
        we don't know the identity scheme).
        """
        if enr.identity_scheme.id not in self.identity_scheme_registry:
            raise ValueError(
                f"ENRs identity scheme with id {enr.identity_scheme.id} unknown to ENR DBs "
                f"identity scheme registry"
            )


class MemoryEnrDb(BaseEnrDb):

    def __init__(self, identity_scheme_registry: IdentitySchemeRegistry):
        super().__init__(identity_scheme_registry)

        self.key_value_storage: Dict[NodeID, ENR] = {}

    async def insert(self, enr: ENR) -> None:
        self.validate_identity_scheme(enr)

        if await self.contains(enr.node_id):
            raise ValueError("ENR with node id %s already exists", encode_hex(enr.node_id))
        else:
            self.logger.debug(
                "Inserting new ENR of %s with sequence number %d",
                encode_hex(enr.node_id),
                enr.sequence_number,
            )
            self.key_value_storage[enr.node_id] = enr

    async def update(self, enr: ENR) -> None:
        self.validate_identity_scheme(enr)
        existing_enr = await self.get(enr.node_id)
        if existing_enr.sequence_number < enr.sequence_number:
            self.logger.debug(
                "Updating ENR of %s from sequence number %d to %d",
                encode_hex(enr.node_id),
                existing_enr.sequence_number,
                enr.sequence_number,
            )
            self.key_value_storage[enr.node_id] = enr
        else:
            self.logger.debug(
                "Not updating ENR of %s as new sequence number %d is not higher than the current "
                "one %d",
                encode_hex(enr.node_id),
                enr.sequence_number,
                existing_enr.sequence_number,
            )

    async def remove(self, node_id: NodeID) -> None:
        self.key_value_storage.pop(node_id)
        self.logger.debug("Removing ENR of %s", encode_hex(node_id))

        await trio.sleep(0)  # add checkpoint to make this a proper async function

    async def insert_or_update(self, enr: ENR) -> None:
        try:
            await self.update(enr)
        except KeyError:
            await self.insert(enr)

    async def get(self, node_id: NodeID) -> ENR:
        await trio.sleep(0)  # add checkpoint to make this a proper async function
        return self.key_value_storage[node_id]

    async def contains(self, node_id: NodeID) -> bool:
        await trio.sleep(0)  # add checkpoint to make this a proper async function
        return node_id in self.key_value_storage
