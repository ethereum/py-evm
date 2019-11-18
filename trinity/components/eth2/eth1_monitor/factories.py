import random

import factory

from eth2.beacon.types.deposit_data import DepositData

from trinity.tools.factories.db import AtomicDBFactory

from .db import DepositDataDB, ListCachedDepositDataDB


class DepositDataDBFactory(factory.Factory):
    class Meta:
        model = DepositDataDB

    db = factory.SubFactory(AtomicDBFactory)


class ListCachedDepositDataDBFactory(factory.Factory):
    class Meta:
        model = ListCachedDepositDataDB

    db = factory.SubFactory(AtomicDBFactory)


MIN_DEPOSIT_AMOUNT = 1000000000  # Gwei
FULL_DEPOSIT_AMOUNT = 32000000000  # Gwei

SAMPLE_PUBKEY = b"\x11" * 48
SAMPLE_WITHDRAWAL_CREDENTIALS = b"\x22" * 32
SAMPLE_VALID_SIGNATURE = b"\x33" * 96


class DepositDataFactory(factory.Factory):
    class Meta:
        model = DepositData

    pubkey = SAMPLE_PUBKEY
    withdrawal_credentials = SAMPLE_WITHDRAWAL_CREDENTIALS
    amount = factory.LazyFunction(
        lambda: random.randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT + 1)
    )
    signature = SAMPLE_VALID_SIGNATURE
