from abc import (
    ABC,
)
from typing import (
    Optional,
    Tuple,
)

from eth_typing import (
    Address,
)

from eth._utils.address import (
    force_bytes_to_address,
)
from eth._utils.state import (
    code_is_delegation_designation,
)
from eth.abc import (
    ComputationAPI,
)
from eth.vm.forks.berlin.logic import (
    BaseCallEIP2929,
    CallCodeEIP2929,
    CallEIP2929,
    DelegateCallEIP2929,
    StaticCallEIP2929,
)


# -- EIP-7702 -- #
class BaseCallEIP7702(BaseCallEIP2929, ABC):
    def get_code_at_address(
        self, computation: ComputationAPI, code_source: Address
    ) -> Tuple[bytes, Optional[Address]]:
        """
        Gets code at address, consumes relevant account load fees, and returns
        (code, delegation_address)
        """
        # consume account load gas for code source address
        self.consume_account_load_gas(computation, code_source)
        code = computation.state.get_code(code_source)

        if code_is_delegation_designation(code):
            delegation = force_bytes_to_address(code[3:])
            # consume account load gas for delegation address
            self.consume_account_load_gas(computation, delegation)
            return computation.state.get_code(delegation), delegation
        else:
            return code, None


class CallEIP7702(CallEIP2929, BaseCallEIP7702):
    ...


class CallCodeEIP7702(CallCodeEIP2929, BaseCallEIP7702):
    ...


class DelegateCallEIP7702(DelegateCallEIP2929, BaseCallEIP7702):
    ...


class StaticCallEIP7702(StaticCallEIP2929, BaseCallEIP7702):
    ...
