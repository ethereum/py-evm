try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from trinity.rlp.block_body import BlockBody

from .headers import BlockHeaderFactory
from .transactions import BaseTransactionFieldsFactory


class BlockBodyFactory(factory.Factory):
    class Meta:
        model = BlockBody

    transactions = factory.LazyFunction(lambda: BaseTransactionFieldsFactory.create_batch(2))
    uncles = factory.LazyFunction(lambda: BlockHeaderFactory.create_batch(2))
