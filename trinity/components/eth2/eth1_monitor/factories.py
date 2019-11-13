import random

import factory

from eth2.beacon.types.deposit_data import DepositData

from trinity.tools.factories.db import AtomicDBFactory

from .db import DepositDataDB


class DepositDataDBFactory(factory.Factory):
    class Meta:
        model = DepositDataDB

    db = factory.SubFactory(AtomicDBFactory)


class DepositDataFactory(factory.Factory):
    class Meta:
        model = DepositData

    amount = factory.LazyFunction(lambda: random.randint(0, 2 ** 32 - 1))
