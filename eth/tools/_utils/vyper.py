import functools

try:
    from vyper.compile_lll import (
        compile_to_assembly,
        assembly_to_evm,
    )
    from vyper.parser.parser_utils import LLLnode
except ImportError:
    vyper_available = False
else:
    vyper_available = True


def require_vyper(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if vyper_available:
            return fn(*args, **kwargs)
        else:
            raise ImportError("The `{0}` function requires the vyper compiler.")
    return inner


@require_vyper
def compile_vyper_lll(vyper_code):
    lll_node = LLLnode.from_list(vyper_code)
    assembly = compile_to_assembly(lll_node)
    code = assembly_to_evm(assembly)
    return code
