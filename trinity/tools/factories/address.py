
try:
    import factory
except ImportError:
    raise ImportError("The p2p.tools.factories module requires the `factory_boy` library.")

import secrets
from typing import Any, Type

from eth_typing import Address


class AddressFactory(factory.Factory):
    class Meta:
        model = bytes

    @classmethod
    def _create(cls,
                model_class: Type[bytes],
                *args: Any,
                **kwargs: Any) -> Address:
        return Address(model_class(secrets.token_bytes(20)))
