try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from typing import (
    Any,
    Type,
)

from eth_utils import to_bytes

from eth.db.header import HeaderDB
from eth.db.backends.memory import MemoryDB
from eth.db.atomic import AtomicDB

from trinity.db.eth1.header import AsyncHeaderDB


MAINNET_GENESIS_HASH = to_bytes(hexstr='0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')  # noqa: E501


class MemoryDBFactory(factory.Factory):
    class Meta:
        model = MemoryDB


class AtomicDBFactory(factory.Factory):
    class Meta:
        model = AtomicDB

    wrapped_db = factory.SubFactory(MemoryDBFactory)


class HeaderDBFactory(factory.Factory):
    class Meta:
        model = HeaderDB

    db = factory.SubFactory(AtomicDBFactory)


class AsyncHeaderDBFactory(factory.Factory):
    class Meta:
        model = AsyncHeaderDB

    db = factory.SubFactory(AtomicDBFactory)

    @classmethod
    def _create(cls,
                model_class: Type[AsyncHeaderDB],
                *args: Any,
                **kwargs: Any) -> AsyncHeaderDB:
        from eth.chains.base import Chain
        from eth.tools.builder.chain import build, latest_mainnet_at, genesis

        genesis_params = kwargs.pop('genesis_params', None)

        headerdb = model_class(*args, **kwargs)

        # SIDE EFFECT!
        # This uses the side effect of initializing a chain using the `builder`
        # tool to populate the genesis state into the database.
        build(
            Chain,
            latest_mainnet_at(0),
            genesis(db=headerdb.db, params=genesis_params),
        )
        return headerdb
