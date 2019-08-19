import pytest

from p2p.discv5.enr_db import (
    MemoryEnrDb,
)
from p2p.discv5.identity_schemes import (
    default_identity_scheme_registry,
    IdentitySchemeRegistry,
)

from p2p.tools.factories.discovery import (
    ENRFactory,
)
from p2p.tools.factories.keys import (
    PrivateKeyFactory,
)


@pytest.fixture
def memory_db():
    return MemoryEnrDb(default_identity_scheme_registry)


@pytest.mark.trio
async def test_memory_insert(memory_db):
    private_key = PrivateKeyFactory().to_bytes()
    enr = ENRFactory(private_key=private_key)

    await memory_db.insert(enr)
    assert await memory_db.contains(enr.node_id)
    assert await memory_db.get(enr.node_id) == enr

    with pytest.raises(ValueError):
        await memory_db.insert(enr)

    updated_enr = ENRFactory(private_key=private_key, sequence_number=enr.sequence_number + 1)
    with pytest.raises(ValueError):
        await memory_db.insert(updated_enr)


@pytest.mark.trio
async def test_memory_update(memory_db):
    private_key = PrivateKeyFactory().to_bytes()
    enr = ENRFactory(private_key=private_key)

    with pytest.raises(KeyError):
        await memory_db.update(enr)

    await memory_db.insert(enr)

    await memory_db.update(enr)
    assert await memory_db.get(enr.node_id) == enr

    updated_enr = ENRFactory(private_key=private_key, sequence_number=enr.sequence_number + 1)
    await memory_db.update(updated_enr)
    assert await memory_db.get(enr.node_id) == updated_enr


@pytest.mark.trio
async def test_memory_insert_or_update(memory_db):
    private_key = PrivateKeyFactory().to_bytes()
    enr = ENRFactory(private_key=private_key)

    await memory_db.insert_or_update(enr)
    assert await memory_db.get(enr.node_id) == enr

    await memory_db.insert_or_update(enr)
    assert await memory_db.get(enr.node_id) == enr

    updated_enr = ENRFactory(private_key=private_key, sequence_number=enr.sequence_number + 1)
    await memory_db.insert_or_update(updated_enr)
    assert await memory_db.get(enr.node_id) == updated_enr


@pytest.mark.trio
async def test_memory_remove(memory_db):
    enr = ENRFactory()

    with pytest.raises(KeyError):
        await memory_db.remove(enr.node_id)

    await memory_db.insert(enr)
    await memory_db.remove(enr.node_id)

    assert not await memory_db.contains(enr.node_id)


@pytest.mark.trio
async def test_memory_get(memory_db):
    enr = ENRFactory()

    with pytest.raises(KeyError):
        await memory_db.get(enr.node_id)

    await memory_db.insert(enr)
    assert await memory_db.get(enr.node_id) == enr


@pytest.mark.trio
async def test_memory_contains(memory_db):
    enr = ENRFactory()

    assert not await memory_db.contains(enr.node_id)
    await memory_db.insert(enr)
    assert await memory_db.contains(enr.node_id)


@pytest.mark.trio
async def test_memory_checks_identity_scheme():
    empty_identity_scheme_registry = IdentitySchemeRegistry()
    memory_db = MemoryEnrDb(empty_identity_scheme_registry)
    enr = ENRFactory()

    with pytest.raises(ValueError):
        await memory_db.insert(enr)
    with pytest.raises(ValueError):
        await memory_db.insert_or_update(enr)
