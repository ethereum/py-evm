from typing import (
    Any,
    Dict,
    Optional,
)

from eth_utils.toolz import (
    assoc_in,
    merge,
)

from eth.tools._utils.git import (
    get_version_from_git,
)
from eth.tools.fixtures.helpers import (
    get_test_name,
)

from .formatters import (
    filled_state_test_formatter,
    filled_vm_test_formatter,
)
from .state import (
    fill_state_test,
)
from .vm import (
    fill_vm_test,
)


#
# Primary test filler
#
def fill_test(
    filler: Dict[str, Any],
    info: Optional[Dict[str, Any]] = None,
    apply_formatter: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    test_name = get_test_name(filler)
    test = filler[test_name]

    if "transaction" in test:
        filled = fill_state_test(filler)
        formatter = filled_state_test_formatter
    elif "exec" in test:
        filled = fill_vm_test(filler, **kwargs)
        formatter = filled_vm_test_formatter
    else:
        raise ValueError("Given filler does not appear to be for VM or state test")

    info = merge(
        {"filledwith": f"py-evm-{get_version_from_git()}"},
        info if info else {},
    )
    filled = assoc_in(filled, [test_name, "_info"], info)

    if apply_formatter:
        return formatter(filled)
    else:
        return filled
