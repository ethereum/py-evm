import functools
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Tuple,
)

try:
    from vyper.compile_lll import (
        assembly_to_evm,
        compile_to_assembly,
    )
    from vyper.parser.parser_utils import (
        LLLnode,
    )
except ImportError:
    vyper_available = False
else:
    vyper_available = True


def require_vyper(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Any:
        if vyper_available:
            return fn(*args, **kwargs)
        else:
            raise ImportError("The `{0}` function requires the vyper compiler.")

    return inner


@require_vyper
def compile_vyper_lll(vyper_code: List[Any]) -> Tuple[bytes, Dict[str, Any]]:
    lll_node = LLLnode.from_list(vyper_code)
    assembly = compile_to_assembly(lll_node)
    code = assembly_to_evm(assembly)
    return code
