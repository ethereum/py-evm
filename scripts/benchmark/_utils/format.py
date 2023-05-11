from eth_utils import (
    encode_hex,
)

from eth.rlp.blocks import (
    BaseBlock,
)


def format_block(block: BaseBlock) -> str:
    return (
        "\n\n"
        "------------------------Block------------------------------------\n"
        f"Number #{block.number:>12} Hash {encode_hex(block.hash)}\n"
        "-----------------------------------------------------------------\n"
    )
