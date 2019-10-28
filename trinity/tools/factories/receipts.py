try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

from eth.constants import BLANK_ROOT_HASH
from eth.rlp.receipts import Receipt


class ReceiptFactory(factory.Factory):
    class Meta:
        model = Receipt

    state_root = BLANK_ROOT_HASH
    gas_used = 0
    bloom = 0
    logs = ()
