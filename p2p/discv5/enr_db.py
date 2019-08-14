from abc import ABC
from typing import (
    Dict,
)

import trio

from p2p.discv5.enr import ENR
from p2p.discv5.identity_schemes import IdentitySchemeRegistry
from p2p.discv5.typing import NodeID


class EnrDbApi(ABC):

    def __init__(self, identity_scheme_registry: IdentitySchemeRegistry):
        self.identity_scheme_registry = identity_scheme_registry

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

    async def insert(self, enr: ENR) -> None:
        """Insert an ENR into the database."""
        ...

    async def update(self, enr: ENR) -> None:
        """Update an existing ENR if the sequence number is greater."""
        ...

    async def remove(self, node_id: NodeID) -> None:
        """Remove an ENR from the db."""
        ...

    async def insert_or_update(self, enr: ENR) -> None:
        """Insert or update an ENR depending if it is already present already or not."""
        ...

    async def get(self, node_id: NodeID) -> ENR:
        """Get an ENR by its node id."""
        ...

    async def contains(self, node_id: NodeID) -> bool:
        """Check if the db contains an ENR with the given node id."""
        ...


class MemoryEnrDb(EnrDbApi):

    def __init__(self, identity_scheme_registry: IdentitySchemeRegistry):
        self.identity_scheme_registry = identity_scheme_registry
        self.key_value_storage: Dict[NodeID, ENR] = {}

    async def insert(self, enr: ENR) -> None:
        self.validate_identity_scheme(enr)

        if await self.contains(enr.node_id):
            raise ValueError(f"ENR with nodeid {enr.node_id} already exists.")
        else:
            self.key_value_storage[enr.node_id] = enr

    async def update(self, enr: ENR) -> None:
        self.validate_identity_scheme(enr)
        existing_enr = await self.get(enr.node_id)
        if existing_enr.sequence_number < enr.sequence_number:
            self.key_value_storage[enr.node_id] = enr

    async def remove(self, node_id: NodeID) -> None:
        self.key_value_storage.pop(node_id)

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
